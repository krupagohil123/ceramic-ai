const express = require("express");
const cors = require("cors");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const axios = require("axios");
const FormData = require("form-data");
const crypto = require("crypto");

const app = express();
const productsFilePath = path.join(__dirname, "data", "products.json");
const aiServiceUrl = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";

function loadExtractedProducts() {
  try {
    const products = JSON.parse(fs.readFileSync(productsFilePath, "utf8"));
    if (!Array.isArray(products)) {
      throw new Error("Product store must contain a JSON array");
    }
    return products;
  } catch (error) {
    if (error.code === "ENOENT") {
      return [];
    }
    throw error;
  }
}

function persistExtractedProducts(products) {
  fs.mkdirSync(path.dirname(productsFilePath), { recursive: true });
  const temporaryPath = `${productsFilePath}.${process.pid}.tmp`;
  fs.writeFileSync(temporaryPath, `${JSON.stringify(products, null, 2)}\n`, "utf8");
  fs.renameSync(temporaryPath, productsFilePath);
}

function productIdentity(product) {
  const identityFields = [
    product.sourceFile,
    product.sourcePage,
    product.productCode,
    product.productName,
    product.category,
    product.collection,
    product.size,
    product.surface,
    product.finish,
    product.color,
  ];

  return JSON.stringify(identityFields.map((value) => {
    if (Array.isArray(value)) {
      return value.map((item) => String(item ?? "").trim().toLowerCase()).sort();
    }
    return String(value ?? "").trim().toLowerCase();
  }));
}

function mergeExtractedProducts(existingProducts, incomingProducts) {
  const mergedProducts = [...existingProducts];
  const productIndexes = new Map(
    mergedProducts.map((product, index) => [productIdentity(product), index])
  );

  for (const product of incomingProducts) {
    const identity = productIdentity(product);
    const existingIndex = productIndexes.get(identity);

    if (existingIndex === undefined) {
      productIndexes.set(identity, mergedProducts.length);
      mergedProducts.push(product);
      continue;
    }

    const existingProduct = mergedProducts[existingIndex];
    mergedProducts[existingIndex] = {
      ...existingProduct,
      ...product,
      image: product.image || existingProduct.image || null,
    };
  }

  return mergedProducts;
}

let extractedProducts = loadExtractedProducts();

app.use(cors());
app.use(express.json());

// =====================================================
// Static Files: Extracted Images
// =====================================================

const extractedImagesDir = path.join(
  __dirname,
  "..",
  "ai-service",
  "extracted_images"
);

if (!fs.existsSync(extractedImagesDir)) {
  fs.mkdirSync(extractedImagesDir, { recursive: true });
}

app.use(
  "/extracted_images",
  express.static(extractedImagesDir)
);

// =====================================================
// Upload Folder Configuration
// =====================================================

const uploadDir = path.join(__dirname, "upload");

if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const safeName = file.originalname.replace(/[^a-zA-Z0-9.-]/g, "_");
    const uniqueName = `${Date.now()}-${crypto.randomUUID()}-${safeName}`;
    cb(null, uniqueName);
  },
});

const upload = multer({
  storage,
  limits: {
    files: 50,
    fileSize: 100 * 1024 * 1024, // 100 MB max per file
  },
  fileFilter: (req, file, cb) => {
    if (file.mimetype === "application/pdf" || file.originalname.toLowerCase().endsWith(".pdf")) {
      cb(null, true);
    } else {
      cb(new Error("Only PDF files are allowed"));
    }
  },
});

// =====================================================
// Node → Python PDF Extraction Helper
// =====================================================

async function processPdfWithPython(file) {
  const filename = path.basename(file.filename || "");
  const fileName = file.fileName || filename;
  const filePath = path.join(uploadDir, filename);

  if (!filename || !filename.toLowerCase().endsWith(".pdf") || !fs.existsSync(filePath)) {
    return {
      success: false,
      filename: filename,
      fileName,
      status: "error",
      products: [],
      productCount: 0,
      errors: ["File not found on server"],
    };
  }

  try {
    const fileBuffer = fs.readFileSync(filePath);
    const form = new FormData();

    form.append("file", fileBuffer, {
      filename,
      contentType: "application/pdf",
    });

    console.log(`➡️ [AI Service] Forwarding PDF: ${filename} (${(fileBuffer.length / 1024 / 1024).toFixed(2)} MB)`);

    const response = await axios.post(
      `${aiServiceUrl}/extract`,
      form,
      {
        headers: {
          ...form.getHeaders(),
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        timeout: 600000, // 10 minutes timeout
      }
    );

    console.log(`✅ [AI Service] Extraction completed for: ${filename} (${response.data.totalProducts || 0} products)`);

    const products = Array.isArray(response.data?.products)
      ? response.data.products.map((product) => ({
          productCode: product.productCode ?? null,
          productName: product.productName ?? null,
          category: product.category ?? null,
          collection: product.collection ?? null,
          size: product.size ?? null,
          surface: product.surface ?? null,
          finish: product.finish ?? null,
          color: product.color ?? null,
          image: product.image ?? null,
          sourceFile: fileName,
          sourcePage: product.sourcePage ?? product.pages?.[0] ?? null,
          pages: Array.isArray(product.pages) ? product.pages : [],
        }))
      : [];

    return {
      success: true,
      filename,
      fileName,
      status: "success",
      products,
      productCount: products.length,
      errors: [],
    };

  } catch (error) {
    console.error(
      `❌ [AI Service] Extraction failed for ${filename}:`,
      error.response?.data?.detail || error.message
    );

    return {
      success: false,
      filename: filename,
      fileName,
      status: "error",
      products: [],
      productCount: 0,
      errors: [
        error.response?.data?.detail ||
        error.message ||
        "AI service processing error",
      ],
    };
  }
}

// =====================================================
// ROOT & HEALTH ENDPOINTS
// =====================================================

app.get("/", (req, res) => {
  res.json({
    success: true,
    message: "Ceramic AI Backend is running",
    version: "2.0.0",
  });
});

app.get("/api/ai-test", async (req, res) => {
  try {
    const response = await axios.get(`${aiServiceUrl}/health`, { timeout: 5000 });
    return res.json({
      success: true,
      message: "Node.js connected to Python AI service successfully",
      python: response.data,
    });
  } catch (error) {
    return res.status(500).json({
      success: false,
      message: "Could not connect to Python AI service",
      error: error.message,
    });
  }
});

// =====================================================
// PDF UPLOAD API (Fast, reliable Multer ingestion)
// =====================================================

app.post(
  "/api/upload",
  upload.array("pdfs", 50),
  async (req, res) => {
    try {
      if (!req.files || req.files.length === 0) {
        return res.status(400).json({
          success: false,
          message: "No PDF files uploaded",
        });
      }

      const uploadedFiles = req.files.map((file) => ({
        originalName: file.originalname,
        filename: file.filename,
        path: file.path,
        size: file.size,
      }));

      console.log(`📥 Uploaded ${uploadedFiles.length} file(s) successfully.`);

      return res.json({
        success: true,
        message: `${uploadedFiles.length} PDF(s) uploaded successfully`,
        totalFiles: uploadedFiles.length,
        files: uploadedFiles,
      });

    } catch (error) {
      console.error("PDF upload error:", error);
      return res.status(500).json({
        success: false,
        message: "PDF upload failed",
        error: error.message,
      });
    }
  }
);

// =====================================================
// MULTI-PDF AI EXTRACTION API
// =====================================================

app.post("/api/ai-extract", async (req, res) => {
  try {
    const requestedFiles = Array.isArray(req.body?.files)
      ? req.body.files
      : Array.isArray(req.body?.filenames)
        ? req.body.filenames.map((filename) => ({ filename }))
        : fs.readdirSync(uploadDir)
          .filter((filename) => filename.toLowerCase().endsWith(".pdf"))
          .map((filename) => ({ filename }));
    const filesToProcess = requestedFiles.map((file) => {
      const filename = typeof file === "string" ? file : String(file?.filename || "");
      const fileName = typeof file === "object" && file?.fileName
        ? String(file.fileName)
        : filename;
      return {
        filename,
        fileName,
        invalid: !filename || path.basename(filename) !== filename || !filename.toLowerCase().endsWith(".pdf"),
      };
    });

    if (filesToProcess.length === 0) {
      return res.status(404).json({
        success: false,
        message: "No PDF files found to process",
      });
    }

    console.log(`📚 Starting AI extraction on ${filesToProcess.length} PDF file(s)...`);

    // Process each PDF in its own Python request so one failure cannot stop the batch.
    const results = [];
    const combinedProducts = [];

    for (let i = 0; i < filesToProcess.length; i++) {
      const file = filesToProcess[i];
      if (file.invalid) {
        results.push({
          success: false,
          filename: file.filename,
          fileName: file.fileName,
          status: "error",
          products: [],
          productCount: 0,
          errors: ["Invalid uploaded PDF identifier"],
        });
        continue;
      }

      const filename = file.filename;
      console.log(`🚀 [${i + 1}/${filesToProcess.length}] Processing: ${filename}`);

      const result = await processPdfWithPython(file);
      results.push(result);

      if (result.success) {
        combinedProducts.push(...result.products);
      }
    }

    if (combinedProducts.length > 0) {
      const mergedProducts = mergeExtractedProducts(extractedProducts, combinedProducts);
      persistExtractedProducts(mergedProducts);
      extractedProducts = mergedProducts;
    }

    const successfulCount = results.filter((r) => r.success).length;
    const failedCount = results.filter((r) => !r.success).length;

    console.log(`Extraction finished: ${successfulCount} succeeded, ${failedCount} failed. Total products: ${combinedProducts.length}`);

    return res.json({
      success: true,
      message: "AI extraction completed",
      totalFiles: results.length,
      successfulFiles: successfulCount,
      failedFiles: failedCount,
      totalProducts: combinedProducts.length,
      products: combinedProducts,
      files: results,
    });

  } catch (error) {
    console.error("❌ AI extraction endpoint error:", error.message);
    return res.status(500).json({
      success: false,
      message: "AI extraction failed",
      error: error.message,
    });
  }
});

// =====================================================
// GET EXTRACTED PRODUCTS API
// =====================================================

app.get("/api/products", (req, res) => {
  try {
    return res.json({
      success: true,
      totalProducts: extractedProducts.length,
      products: extractedProducts,
    });
  } catch (error) {
    console.error("Products API error:", error);
    return res.status(500).json({
      success: false,
      message: "Failed to get products",
      error: error.message,
    });
  }
});

// =====================================================
// CLEAR UPLOADED PDFS API
// =====================================================

app.delete("/api/clear", (req, res) => {
  try {
    const files = fs.readdirSync(uploadDir);
    let deletedCount = 0;

    for (const file of files) {
      if (file.toLowerCase().endsWith(".pdf")) {
        fs.unlinkSync(path.join(uploadDir, file));
        deletedCount++;
      }
    }

    persistExtractedProducts([]);
    extractedProducts = [];

    return res.json({
      success: true,
      message: "Uploaded PDFs and extracted products cleared successfully",
      deletedFiles: deletedCount,
    });
  } catch (error) {
    console.error("Clear upload error:", error);
    return res.status(500).json({
      success: false,
      message: "Failed to clear uploaded PDFs",
      error: error.message,
    });
  }
});

// =====================================================
// GLOBAL ERROR HANDLER
// =====================================================

app.use((err, req, res, next) => {
  console.error("Server error:", err);
  return res.status(400).json({
    success: false,
    message: err.message,
  });
});

// =====================================================
// START SERVER
// =====================================================

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`Ceramic AI Backend running on http://localhost:${PORT}`);
});