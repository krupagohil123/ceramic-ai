const express = require("express");
const cors = require("cors");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const axios = require("axios");
const FormData = require("form-data");

const app = express();
let extractedProducts = [];

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
    const uniqueName = `${Date.now()}-${safeName}`;
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

async function processPdfWithPython(filename) {
  const filePath = path.join(uploadDir, filename);

  if (!fs.existsSync(filePath)) {
    return {
      success: false,
      filename: filename,
      error: "File not found on server",
    };
  }

  try {
    const fileBuffer = fs.readFileSync(filePath);
    const form = new FormData();

    form.append("file", fileBuffer, {
      filename: filename,
      contentType: "application/pdf",
    });

    console.log(`➡️ [AI Service] Forwarding PDF: ${filename} (${(fileBuffer.length / 1024 / 1024).toFixed(2)} MB)`);

    const response = await axios.post(
      "http://127.0.0.1:8000/extract",
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

    return {
      success: true,
      filename: filename,
      pythonResult: response.data,
    };

  } catch (error) {
    console.error(
      `❌ [AI Service] Extraction failed for ${filename}:`,
      error.response?.data?.detail || error.message
    );

    return {
      success: false,
      filename: filename,
      error:
        error.response?.data?.detail ||
        error.message ||
        "AI service processing error",
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
    const response = await axios.get("http://127.0.0.1:8000/health", { timeout: 5000 });
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
    // 1. Determine which files to process
    let filesToProcess = [];

    if (Array.isArray(req.body?.filenames) && req.body.filenames.length > 0) {
      filesToProcess = req.body.filenames;
    } else {
      filesToProcess = fs
        .readdirSync(uploadDir)
        .filter((file) => file.toLowerCase().endsWith(".pdf"));
    }

    if (filesToProcess.length === 0) {
      return res.status(404).json({
        success: false,
        message: "No PDF files found to process",
      });
    }

    console.log(`📚 Starting AI extraction on ${filesToProcess.length} PDF file(s)...`);

    // 2. Process files sequentially to ensure 100% stability and zero stream drops
    const results = [];
    const newExtractedProducts = [];

    for (let i = 0; i < filesToProcess.length; i++) {
      const filename = filesToProcess[i];
      console.log(`🚀 [${i + 1}/${filesToProcess.length}] Processing: ${filename}`);

      const result = await processPdfWithPython(filename);
      results.push(result);

      if (result.success && Array.isArray(result.pythonResult?.products)) {
        const fileProducts = result.pythonResult.products.map((product) => ({
          ...product,
          sourceFile: result.filename,
        }));
        newExtractedProducts.push(...fileProducts);
      }
    }

    // Append to in-memory store (or replace if requested)
    extractedProducts = newExtractedProducts;

    const successfulCount = results.filter((r) => r.success).length;
    const failedCount = results.filter((r) => !r.success).length;

    console.log(`🎉 Extraction finished: ${successfulCount} succeeded, ${failedCount} failed. Total products: ${extractedProducts.length}`);

    return res.json({
      success: true,
      message: "AI extraction completed",
      totalFiles: results.length,
      successfulFiles: successfulCount,
      failedFiles: failedCount,
      totalProducts: extractedProducts.length,
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

    extractedProducts = [];

    return res.json({
      success: true,
      message: "Uploaded PDFs cleared successfully",
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

const PORT = 5000;

app.listen(PORT, () => {
  console.log(`Ceramic AI Backend running on http://localhost:${PORT}`);
});