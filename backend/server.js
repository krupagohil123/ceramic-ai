const express = require("express");
const cors = require("cors");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const axios = require("axios");
const FormData = require("form-data");


const pdfParseModule = require("pdf-parse");
const pdfParse = pdfParseModule.default || pdfParseModule;

const app = express();
let extractedProducts = [];

app.use(cors());
app.use(express.json());
const extractedImagesDir = path.join(
  __dirname,
  "..",
  "ai-service",
  "extracted_images"
);

app.use(
  "/extracted_images",
  express.static(extractedImagesDir)
);
// =====================================================
// Upload Folder
// =====================================================

const uploadDir = path.join(__dirname, "upload");

if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

// =====================================================
// Multer Configuration
// =====================================================

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, uploadDir);
  },

  filename: (req, file, cb) => {
    const uniqueName =
      Date.now() +
      "-" +
      file.originalname.replace(/\s+/g, "_");

    cb(null, uniqueName);
  },
});

const upload = multer({
  storage,

  limits: {
    files: 50,
    fileSize: 50 * 1024 * 1024,
  },

  fileFilter: (req, file, cb) => {
    if (file.mimetype === "application/pdf") {
      cb(null, true);
    } else {
      cb(new Error("Only PDF files are allowed"));
    }
  },
});
// =====================================================
// Node → Python PDF Extraction
// =====================================================
async function processPdfWithPython(filename) {
  const filePath = path.join(uploadDir, filename);

  try {
    const form = new FormData();

    form.append("file", fs.createReadStream(filePath), {
      filename: filename,
      contentType: "application/pdf",
    });

    console.log("➡️ Sending PDF to Python:", filename);

    const response = await axios.post(
      "http://127.0.0.1:8000/extract",
      form,
      {
        headers: {
          ...form.getHeaders(),
        },
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        timeout: 600000,
      }
    );

    console.log("✅ Python response received:", filename);

    return {
      success: true,
      filename: filename,
      pythonResult: response.data,
    };

  } catch (error) {
    console.error(
      `❌ Python extraction failed for ${filename}:`,
      error.response?.data || error.message
    );

    return {
      success: false,
      filename: filename,
      error:
        error.response?.data?.detail ||
        error.message,
    };
  }
}
app.post("/api/ai-extract", async (req, res) => {
  try {
    extractedProducts = [];

    const files = fs
      .readdirSync(uploadDir)
      .filter((file) =>
        file.toLowerCase().endsWith(".pdf")
      );

    if (files.length === 0) {
      return res.status(404).json({
        success: false,
        message: "No PDF files found in upload folder",
      });
    }

    console.log(
      `📚 Total PDFs found: ${files.length}`
    );

    // ==========================================
    // Controlled parallel processing
    // ==========================================

    const BATCH_SIZE = 3;
    const results = [];

    for (
      let i = 0;
      i < files.length;
      i += BATCH_SIZE
    ) {
      const batch = files.slice(
        i,
        i + BATCH_SIZE
      );

      console.log(
        `🚀 Processing batch ${
          Math.floor(i / BATCH_SIZE) + 1
        }:`,
        batch
      );

      const batchResults = await Promise.all(
        batch.map((filename) =>
          processPdfWithPython(filename)
        )
      );

      results.push(...batchResults);

      // ==========================================
      // Add successful products
      // ==========================================

      for (const result of batchResults) {
        if (
          result.success &&
          Array.isArray(
            result.pythonResult?.products
          )
        ) {
          extractedProducts.push(
            ...result.pythonResult.products.map(
              (product) => ({
                ...product,
                sourceFile: result.filename,
              })
            )
          );
        }
      }
    }

    console.log(
      `🎉 Processing completed: ${results.length} PDFs`
    );

    console.log(
      `📦 Total products: ${extractedProducts.length}`
    );

    return res.json({
      success: true,
      message:
        "Multiple PDFs processed successfully",

      totalFiles: results.length,

      successfulFiles:
        results.filter(
          (result) => result.success
        ).length,

      failedFiles:
        results.filter(
          (result) => !result.success
        ).length,

      totalProducts:
        extractedProducts.length,

      files: results,
    });

  } catch (error) {
    console.error(
      "❌ AI extraction error:",
      error.message
    );

    return res.status(500).json({
      success: false,
      message: "AI extraction failed",
      error: error.message,
    });
  }
});
// =====================================================
// Get Extracted Products
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
// Product Names Specifically Found in Catalogue
// =====================================================

const validProductNames = [
  "Gomma Camo",
  "River Grey",
  "Ash Brown",
  "Silver Chalk",
  "White Sand",
  "Lime Stone",
  "Yellow Ocra",
  "Terra Red",
  "Burnt Brick",
  "Cocoa Mud",
  "Black Beach",
  "Deep Verde",
  "Queen Mint",
];

// =====================================================
// Detect Product Names
// =====================================================

function detectProductNames(text) {
  const foundProducts = [];

  // ---------------------------------------------------
  // Normalize PDF text
  // ---------------------------------------------------

  const normalizedText = text
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ");

  // ---------------------------------------------------
  // First: Look for exact known product names
  // ---------------------------------------------------

  for (const productName of validProductNames) {
    const regex = new RegExp(
      `(^|\\n|\\s)${productName.replace(
        /[-/\\^$*+?.()|[\]{}]/g,
        "\\$&"
      )}(?=\\s|\\n|$)`,
      "gi"
    );

    if (regex.test(normalizedText)) {
      foundProducts.push(productName);
    }
  }

  // ---------------------------------------------------
  // Also check line-by-line
  // ---------------------------------------------------

  const lines = normalizedText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  for (const line of lines) {
    const cleanLine = line
      .replace(/\s+/g, " ")
      .trim();

    // Exact match only
    for (const productName of validProductNames) {
      if (
        cleanLine.toLowerCase() ===
        productName.toLowerCase()
      ) {
        foundProducts.push(productName);
      }
    }
  }

  // ---------------------------------------------------
  // Remove duplicates
  // ---------------------------------------------------

  return [...new Set(foundProducts)];
}

// =====================================================
// Product Parser
// =====================================================

function extractProductsFromText(text) {
  const products = [];

  // ===================================================
  // Collection
  // ===================================================

  let collection = null;

  if (/COURTYARD/i.test(text)) {
    collection = "COURTYARD";
  }

  // ===================================================
  // Category
  // ===================================================

  let category = null;

  const categoryMatch = text.match(
    /\b(FULLBODY\s+VITRIFIED\s+TILES|FULL\s+BODY\s+TILES|VITRIFIED\s+TILES)\b/i
  );

  if (categoryMatch) {
    category = categoryMatch[1]
      .replace(/\s+/g, " ")
      .trim()
      .toUpperCase();
  }

  // ===================================================
  // Sizes
  // ===================================================

  const sizeMatches =
    text.match(
      /\b\d{3,4}\s*[x×]\s*\d{3,4}\s*mm\b/gi
    ) || [];

  const sizes = [
    ...new Set(
      sizeMatches.map((size) =>
        size
          .replace(/\s+/g, "")
          .replace("×", "x")
          .toLowerCase()
      )
    ),
  ];

  // ===================================================
  // Finish
  // ===================================================

  const finishes = [];

  if (/PROTECT/i.test(text)) {
    finishes.push("Protect");
  }

  if (/POLISHED/i.test(text)) {
    finishes.push("Polished");
  }

  if (/MATT/i.test(text)) {
    finishes.push("Matt");
  }

  // Remove duplicate finishes
  const uniqueFinishes = [
    ...new Set(finishes),
  ];

  // ===================================================
  // Detect Product Names
  // ===================================================

  const genericProductNames =
    detectProductNames(text);

  // ===================================================
  // Create Product Objects
  // ===================================================

  for (const name of genericProductNames) {
    products.push({
      sku: null,

      productName: name,

      productCode: null,

      category: category,

      collection: collection,

      size:
        sizes.length > 0
          ? sizes
          : null,

      finish:
        uniqueFinishes.length > 0
          ? uniqueFinishes
          : null,

      color: null,

      design: null,

      image: null,
    });
  }

  // ===================================================
  // Remove Duplicate Products
  // ===================================================

  const uniqueProducts =
    products.filter(
      (product, index, self) =>
        index ===
        self.findIndex(
          (item) =>
            item.productName.toLowerCase() ===
            product.productName.toLowerCase()
        )
    );

  // ===================================================
  // Return
  // ===================================================

  return {
    collection,

    category,

    sizes,

    finishes: uniqueFinishes,

    genericProductNames,

    products: uniqueProducts,
  };
}

// =====================================================
// Test Route
// =====================================================

app.get("/", (req, res) => {
  res.json({
    success: true,
    message: "Ceramic AI Backend is running",
  });
});
// =====================================================
// Node → Python AI Service Test
// =====================================================

app.get("/api/ai-test", async (req, res) => {
  try {
    const response = await axios.get(
      "http://127.0.0.1:8000/health"
    );

    return res.json({
      success: true,
      message: "Node.js connected to Python AI service successfully",
      python: response.data,
    });

  } catch (error) {
    console.error(
      "Python AI service connection error:",
      error.message
    );

    return res.status(500).json({
      success: false,
      message: "Could not connect to Python AI service",
      error: error.message,
    });
  }
});
// =====================================================
// PDF Upload API
// =====================================================

app.post(
  "/api/upload",
  upload.array("pdfs", 50),

  async (req, res) => {
    try {
      // -------------------------------------------------
      // Check files
      // -------------------------------------------------

      if (
        !req.files ||
        req.files.length === 0
      ) {
        return res.status(400).json({
          success: false,
          message: "No PDF files uploaded",
        });
      }

      const processedFiles = [];

      // -------------------------------------------------
      // Process uploaded PDFs
      // -------------------------------------------------

      for (const file of req.files) {
        try {
          const pdfBuffer =
            fs.readFileSync(file.path);

          const pdfData =
            await pdfParse(pdfBuffer);

          processedFiles.push({
            originalName:
              file.originalname,

            filename:
              file.filename,

            path:
              file.path,

            size:
              file.size,

            pages:
              pdfData.numpages,

            textLength:
              pdfData.text.length,

            text:
              pdfData.text,
          });

        } catch (fileError) {
          processedFiles.push({
            originalName:
              file.originalname,

            filename:
              file.filename,

            status: "failed",

            error:
              fileError.message,
          });
        }
      }

      // -------------------------------------------------
      // Response
      // -------------------------------------------------

      return res.json({
        success: true,

        message:
          "PDF uploaded and text extracted successfully",

        totalFiles:
          processedFiles.length,

        files:
          processedFiles,
      });

    } catch (error) {
      console.error(
        "PDF processing error:",
        error
      );

      return res.status(500).json({
        success: false,

        message:
          "PDF processing failed",

        error:
          error.message,
      });
    }
  }
);

// =====================================================
// Product Extraction API
// =====================================================

app.post(
  "/api/extract",
  async (req, res) => {
    try {
      // -------------------------------------------------
      // Find PDFs
      // -------------------------------------------------

      const files =
        fs
          .readdirSync(uploadDir)
          .filter((file) =>
            file
              .toLowerCase()
              .endsWith(".pdf")
          );

      // -------------------------------------------------
      // No PDFs
      // -------------------------------------------------

      if (files.length === 0) {
        return res.status(404).json({
          success: false,

          message:
            "No PDF files found in upload folder",
        });
      }

      const results = [];

      // -------------------------------------------------
      // Process every PDF
      // -------------------------------------------------

      for (const filename of files) {
        try {
          const filePath =
            path.join(
              uploadDir,
              filename
            );

          const pdfBuffer =
            fs.readFileSync(
              filePath
            );

          const pdfData =
            await pdfParse(
              pdfBuffer
            );

          // ------------------------------------------------
          // Clean PDF text
          // ------------------------------------------------

          const cleanedText =
            pdfData.text
              .replace(/\r/g, "")
              .replace(/[ \t]+/g, " ")
              .replace(/\n{3,}/g, "\n\n")
              .trim();

          // ------------------------------------------------
          // Extract products
          // ------------------------------------------------

          const extracted =
            extractProductsFromText(
              cleanedText
            );

          // ------------------------------------------------
          // Store result
          // ------------------------------------------------

          results.push({
            filename:
              filename,

            pages:
              pdfData.numpages,

            textLength:
              cleanedText.length,

            collection:
              extracted.collection,

            category:
              extracted.category,

            sizes:
              extracted.sizes,

            finishes:
              extracted.finishes,

            genericProductNames:
              extracted.genericProductNames,

            totalProducts:
              extracted.products.length,

            products:
              extracted.products,

            text:
              cleanedText,
          });

        } catch (fileError) {
          console.error(
            `Error processing ${filename}:`,
            fileError.message
          );

          results.push({
            filename:
              filename,

            status:
              "failed",

            error:
              fileError.message,

            products:
              [],
          });
        }
      }

      // -------------------------------------------------
      // Final Response
      // -------------------------------------------------

      return res.json({
        success: true,

        message:
          "Product extraction completed successfully",

        totalFiles:
          results.length,

        files:
          results,
      });

    } catch (error) {
      console.error(
        "Extraction error:",
        error
      );

      return res.status(500).json({
        success: false,

        message:
          "Product extraction failed",

        error:
          error.message,
      });
    }
  }
);

// =====================================================
// Clear Uploaded PDFs
// =====================================================

app.delete(
  "/api/clear",
  (req, res) => {
    try {
      const files =
        fs.readdirSync(
          uploadDir
        );

      let deletedCount = 0;

      for (const file of files) {
        if (
          file
            .toLowerCase()
            .endsWith(".pdf")
        ) {
          const filePath =
            path.join(
              uploadDir,
              file
            );

          fs.unlinkSync(
            filePath
          );

          deletedCount++;
        }
      }

      return res.json({
        success: true,

        message:
          "Uploaded PDFs cleared successfully",

        deletedFiles:
          deletedCount,
      });

    } catch (error) {
      console.error(
        "Clear upload error:",
        error
      );

      return res.status(500).json({
        success: false,

        message:
          "Failed to clear uploaded PDFs",

        error:
          error.message,
      });
    }
  }
);

// =====================================================
// Error Handler
// =====================================================

app.use(
  (err, req, res, next) => {
    console.error(
      "Server error:",
      err
    );

    return res.status(400).json({
      success: false,

      message:
        err.message,
    });
  }
);

// =====================================================
// Start Server
// =====================================================

const PORT = 5000;

app.listen(
  PORT,
  () => {
    console.log(
      `Ceramic AI Backend running on http://localhost:${PORT}`
    );
  }
);