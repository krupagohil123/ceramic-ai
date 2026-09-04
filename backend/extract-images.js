const fs = require("fs");
const path = require("path");
const pdfjsLib = require("pdfjs-dist/legacy/build/pdf.mjs");

const uploadDir = path.join(__dirname, "upload");
const outputDir = path.join(__dirname, "uploads", "images");

if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

async function extractImagesFromPDF(pdfPath) {
  const pdfBuffer = new Uint8Array(fs.readFileSync(pdfPath));

  const pdf = await pdfjsLib.getDocument({
    data: pdfBuffer,
  }).promise;

  console.log(`\nPDF: ${path.basename(pdfPath)}`);
  console.log(`Total pages: ${pdf.numPages}`);

  let imageCount = 0;

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {
    const page = await pdf.getPage(pageNumber);
    const operatorList = await page.getOperatorList();

    for (let i = 0; i < operatorList.fnArray.length; i++) {
      const fn = operatorList.fnArray[i];

      if (
        fn === pdfjsLib.OPS.paintImageXObject ||
        fn === pdfjsLib.OPS.paintImageXObjectRepeat
      ) {
        const imageName = `page-${pageNumber}-image-${imageCount}.png`;
        const imagePath = path.join(outputDir, imageName);

        const imageData = operatorList.argsArray[i];

        console.log(
          `Image found: Page ${pageNumber} → ${imageName}`
        );

        try {
          const image = await page.objs.get(imageData[0]);

          if (image && image.data) {
            const width = image.width;
            const height = image.height;
            const data = image.data;

            // RGBA image
            const pngBuffer = createPNGBuffer(
              data,
              width,
              height
            );

            fs.writeFileSync(imagePath, pngBuffer);

            console.log(`Saved: ${imagePath}`);

            imageCount++;
          }
        } catch (error) {
          console.log(
            `Could not extract image on page ${pageNumber}: ${error.message}`
          );
        }
      }
    }
  }

  console.log(`\nTotal images extracted: ${imageCount}`);
}


// =====================================================
// PNG creation
// =====================================================

function createPNGBuffer(data, width, height) {
  const zlib = require("zlib");

  const chunks = [];

  function uint32(value) {
    const buffer = Buffer.alloc(4);
    buffer.writeUInt32BE(value >>> 0, 0);
    return buffer;
  }

  function crc32(buffer) {
    let crc = 0xffffffff;

    for (let i = 0; i < buffer.length; i++) {
      crc ^= buffer[i];

      for (let j = 0; j < 8; j++) {
        crc =
          (crc >>> 1) ^
          (0xedb88320 & -(crc & 1));
      }
    }

    return uint32((crc ^ 0xffffffff) >>> 0);
  }

  function pngChunk(type, data) {
    const typeBuffer = Buffer.from(type);
    const length = uint32(data.length);

    return Buffer.concat([
      length,
      typeBuffer,
      data,
      crc32(Buffer.concat([typeBuffer, data])),
    ]);
  }

  // PNG signature
  chunks.push(
    Buffer.from([
      137,
      80,
      78,
      71,
      13,
      10,
      26,
      10,
    ])
  );

  // IHDR
  const ihdr = Buffer.alloc(13);

  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);

  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  chunks.push(
    pngChunk("IHDR", ihdr)
  );

  // Image data
  const scanlines = [];

  for (let y = 0; y < height; y++) {
    const start = y * width * 4;
    const row = Buffer.alloc(width * 4 + 1);

    row[0] = 0;

    Buffer.from(
      data.buffer,
      data.byteOffset + start,
      width * 4
    ).copy(row, 1);

    scanlines.push(row);
  }

  const compressed = zlib.deflateSync(
    Buffer.concat(scanlines)
  );

  chunks.push(
    pngChunk("IDAT", compressed)
  );

  // IEND
  chunks.push(
    pngChunk("IEND", Buffer.alloc(0))
  );

  return Buffer.concat(chunks);
}


// =====================================================
// MAIN
// =====================================================

async function main() {
  const pdfFiles = fs
    .readdirSync(uploadDir)
    .filter((file) =>
      file.toLowerCase().endsWith(".pdf")
    );

  if (pdfFiles.length === 0) {
    console.log(
      "No PDF found in upload folder."
    );
    return;
  }

  for (const file of pdfFiles) {
    const pdfPath = path.join(
      uploadDir,
      file
    );

    try {
      await extractImagesFromPDF(pdfPath);
    } catch (error) {
      console.error(
        `Error processing ${file}:`,
        error
      );
    }
  }
}

main();