import * as Minio from 'minio';
import fs from 'fs';
import path from 'path';
import { promisify } from 'util';

/**
 * Minio Service for file upload and download operations
 */
export class MinioService {
  constructor(config = {}) {
    // Default configuration
    const defaultConfig = {
      endPoint: 'localhost',
      port: 9000,
      useSSL: false,
      accessKey: 'minioadmin',
      secretKey: 'minioadmin'
    };

    this.config = { ...defaultConfig, ...config };
    this.client = new Minio.Client(this.config);
  }

  /**
   * Check if bucket exists, create if it doesn't
   * @param {string} bucketName - Name of the bucket
   * @returns {Promise<boolean>} - True if bucket exists or was created
   */
  async ensureBucket(bucketName) {
    try {
      const exists = await this.client.bucketExists(bucketName);
      if (!exists) {
        await this.client.makeBucket(bucketName);
        console.log(`🪣 Created bucket: ${bucketName}`);
      }
      return true;
    } catch (error) {
      console.error(`❌ Error ensuring bucket ${bucketName}:`, error.message);
      throw error;
    }
  }

  /**
   * Upload a file to Minio bucket
   * @param {string} bucketName - Name of the bucket
   * @param {string} objectName - Name of the object in the bucket (can include folders)
   * @param {string} filePath - Local file path to upload
   * @param {Object} metadata - Optional metadata for the object
   * @returns {Promise<Object>} - Upload result with etag and other info
   */
  async uploadFile(bucketName, objectName, filePath, metadata = {}) {
    try {
      // Ensure bucket exists
      await this.ensureBucket(bucketName);

      // Check if file exists locally
      if (!fs.existsSync(filePath)) {
        throw new Error(`File not found: ${filePath}`);
      }

      const fileStats = fs.statSync(filePath);
      console.log(`📤 Uploading ${filePath} (${(fileStats.size / 1024 / 1024).toFixed(2)} MB) to ${bucketName}/${objectName}`);

      // Add some default metadata
      const fullMetadata = {
        'Content-Type': this.getContentType(filePath),
        'upload-date': new Date().toISOString(),
        'file-size': fileStats.size.toString(),
        ...this.sanitizeMetadata(metadata)
      };

      const result = await this.client.fPutObject(bucketName, objectName, filePath, fullMetadata);
      
      console.log(`✅ Upload completed: ${bucketName}/${objectName}`);
      console.log(`📋 ETag: ${result.etag}`);

      return {
        success: true,
        etag: result.etag,
        bucketName,
        objectName,
        fileSize: fileStats.size,
        metadata: fullMetadata
      };

    } catch (error) {
      console.error(`❌ Upload failed for ${filePath}:`, error.message);
      throw error;
    }
  }

  /**
   * Download a file from Minio bucket
   * @param {string} bucketName - Name of the bucket
   * @param {string} objectName - Name of the object in the bucket
   * @param {string} downloadPath - Local path where file should be downloaded
   * @returns {Promise<Object>} - Download result
   */
  async downloadFile(bucketName, objectName, downloadPath) {
    try {
      // Ensure download directory exists
      const downloadDir = path.dirname(downloadPath);
      if (!fs.existsSync(downloadDir)) {
        fs.mkdirSync(downloadDir, { recursive: true });
      }

      console.log(`📥 Downloading ${bucketName}/${objectName} to ${downloadPath}`);

      await this.client.fGetObject(bucketName, objectName, downloadPath);

      const fileStats = fs.statSync(downloadPath);
      console.log(`✅ Download completed: ${downloadPath} (${(fileStats.size / 1024 / 1024).toFixed(2)} MB)`);

      return {
        success: true,
        bucketName,
        objectName,
        downloadPath,
        fileSize: fileStats.size
      };

    } catch (error) {
      console.error(`❌ Download failed for ${bucketName}/${objectName}:`, error.message);
      throw error;
    }
  }

  /**
   * List objects in a bucket with optional prefix (folder)
   * @param {string} bucketName - Name of the bucket
   * @param {string} prefix - Optional prefix to filter objects (folder path)
   * @param {boolean} recursive - Whether to list recursively
   * @returns {Promise<Array>} - Array of object information
   */
  async listObjects(bucketName, prefix = '', recursive = true) {
    try {
      const objects = [];
      const stream = this.client.listObjects(bucketName, prefix, recursive);

      return new Promise((resolve, reject) => {
        stream.on('data', (obj) => {
          objects.push({
            name: obj.name,
            size: obj.size,
            lastModified: obj.lastModified,
            etag: obj.etag
          });
        });

        stream.on('error', (error) => {
          console.error(`❌ Error listing objects in ${bucketName}:`, error.message);
          reject(error);
        });

        stream.on('end', () => {
          console.log(`📋 Found ${objects.length} objects in ${bucketName}${prefix ? `/${prefix}` : ''}`);
          resolve(objects);
        });
      });

    } catch (error) {
      console.error(`❌ Error listing objects:`, error.message);
      throw error;
    }
  }

  /**
   * Delete an object from bucket
   * @param {string} bucketName - Name of the bucket
   * @param {string} objectName - Name of the object to delete
   * @returns {Promise<boolean>} - True if deleted successfully
   */
  async deleteObject(bucketName, objectName) {
    try {
      await this.client.removeObject(bucketName, objectName);
      console.log(`🗑️  Deleted: ${bucketName}/${objectName}`);
      return true;
    } catch (error) {
      console.error(`❌ Delete failed for ${bucketName}/${objectName}:`, error.message);
      throw error;
    }
  }

  /**
   * Get object metadata
   * @param {string} bucketName - Name of the bucket
   * @param {string} objectName - Name of the object
   * @returns {Promise<Object>} - Object metadata
   */
  async getObjectMetadata(bucketName, objectName) {
    try {
      const stats = await this.client.statObject(bucketName, objectName);
      return {
        size: stats.size,
        lastModified: stats.lastModified,
        etag: stats.etag,
        metadata: stats.metaData
      };
    } catch (error) {
      // Don't log "not found" as errors - these are expected when files don't exist yet
      if (error.code === 'NotFound' || error.code === 'NoSuchKey' || error.message.includes('Not Found')) {
        throw error; // Re-throw without logging - this is expected behavior
      } else {
        console.error(`❌ Error getting metadata for ${bucketName}/${objectName}:`, error.message);
        throw error;
      }
    }
  }

  /**
   * Get a presigned URL for temporary access to an object
   * @param {string} bucketName - Name of the bucket
   * @param {string} objectName - Name of the object
   * @param {number} expiry - Expiry time in seconds (default: 1 hour)
   * @returns {Promise<string>} - Presigned URL
   */
  async getPresignedUrl(bucketName, objectName, expiry = 3600) {
    try {
      const url = await this.client.presignedGetObject(bucketName, objectName, expiry);
      console.log(`🔗 Generated presigned URL for ${bucketName}/${objectName} (expires in ${expiry}s)`);
      return url;
    } catch (error) {
      console.error(`❌ Error generating presigned URL:`, error.message);
      throw error;
    }
  }

  /**
   * Upload multiple files to a bucket/folder
   * @param {string} bucketName - Name of the bucket
   * @param {Array} files - Array of {filePath, objectName} objects
   * @param {string} folderPrefix - Optional folder prefix
   * @returns {Promise<Array>} - Array of upload results
   */
  async uploadMultipleFiles(bucketName, files, folderPrefix = '') {
    console.log(`🚀 Starting upload of ${files.length} files to ${bucketName}${folderPrefix ? `/${folderPrefix}` : ''}`);
    
    const results = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        console.log(`\n📁 File ${i + 1}/${files.length}: ${file.filePath}`);
        
        const objectName = folderPrefix 
          ? `${folderPrefix}/${file.objectName || path.basename(file.filePath)}`
          : (file.objectName || path.basename(file.filePath));

        const result = await this.uploadFile(bucketName, objectName, file.filePath, file.metadata);
        results.push({ ...result, filePath: file.filePath });
      } catch (error) {
        console.error(`❌ Failed to upload ${file.filePath}:`, error.message);
        results.push({ 
          success: false, 
          filePath: file.filePath, 
          error: error.message 
        });
      }
    }

    // Summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;
    
    console.log(`\n📊 Upload Summary:`);
    console.log(`✅ Successful: ${successful}`);
    console.log(`❌ Failed: ${failed}`);

    return results;
  }

  /**
   * Determine content type based on file extension
   * @param {string} filePath - File path
   * @returns {string} - Content type
   */
  getContentType(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    const contentTypes = {
      '.mp4': 'video/mp4',
      '.mp3': 'audio/mpeg',
      '.wav': 'audio/wav',
      '.avi': 'video/x-msvideo',
      '.mov': 'video/quicktime',
      '.mkv': 'video/x-matroska',
      '.json': 'application/json',
      '.txt': 'text/plain',
      '.pdf': 'application/pdf',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.gif': 'image/gif'
    };

    return contentTypes[ext] || 'application/octet-stream';
  }

  /**
   * Test connection to Minio server
   * @returns {Promise<boolean>} - True if connection is successful
   */
  async testConnection() {
    try {
      // Try to list buckets as a connection test
      await this.client.listBuckets();
      console.log('✅ Minio connection successful');
      return true;
    } catch (error) {
      console.error('❌ Minio connection failed:', error.message);
      return false;
    }
  }

  /**
   * Sanitize metadata values for HTTP headers
   * @param {Object} metadata - Raw metadata object
   * @returns {Object} - Sanitized metadata safe for HTTP headers
   */
  sanitizeMetadata(metadata) {
    const sanitized = {};
    
    for (const [key, value] of Object.entries(metadata)) {
      if (value != null) {
        // Sanitize the value to be safe for HTTP headers
        sanitized[key] = String(value)
          .replace(/[^\x20-\x7E]/g, '')     // Remove non-ASCII printable characters
          .replace(/[\r\n\t]/g, ' ')        // Replace line breaks and tabs with spaces
          .replace(/\s+/g, ' ')             // Collapse multiple spaces
          .trim()
          .substring(0, 255);               // Limit length for header safety
      }
    }
    
    return sanitized;
  }
}

export default MinioService;
