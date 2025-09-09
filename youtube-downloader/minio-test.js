import MinioService from './minio-service.js';
import fs from 'fs';
import path from 'path';
import dotenv from 'dotenv';

// Load environment variables from .env file
dotenv.config();

/**
 * Test suite for MinioService
 */
class MinioServiceTest {
  constructor() {
    // Load configuration from environment variables or use defaults
    const endpoint = process.env.MINIO_ENDPOINT || 'localhost:9000';
    const [endPoint, portStr] = endpoint.includes(':') ? endpoint.split(':') : [endpoint, '9000'];
    const port = parseInt(portStr) || 9000;
    
    this.minioConfig = {
      endPoint: endPoint,
      port: port,
      useSSL: process.env.MINIO_SECURE === 'true',
      accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
      secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin',
      region: process.env.MINIO_REGION || 'us-east-1'
    };

    this.minio = new MinioService(this.minioConfig);
    this.testBucket = process.env.MINIO_BUCKET || 'ai-maker-test';
    this.testFolder = 'test-uploads';
    this.tempDir = './test-temp';
  }

  /**
   * Create temporary test files for testing
   */
  async createTestFiles() {
    console.log('📝 Creating temporary test files...');
    
    if (!fs.existsSync(this.tempDir)) {
      fs.mkdirSync(this.tempDir, { recursive: true });
    }

    // Create a text file
    const textContent = `This is a test file created on ${new Date().toISOString()}\nLine 2\nLine 3`;
    fs.writeFileSync(path.join(this.tempDir, 'test.txt'), textContent);

    // Create a JSON file
    const jsonContent = {
      testData: 'Hello Minio',
      timestamp: new Date().toISOString(),
      numbers: [1, 2, 3, 4, 5],
      nested: {
        property: 'value'
      }
    };
    fs.writeFileSync(path.join(this.tempDir, 'test.json'), JSON.stringify(jsonContent, null, 2));

    // Create a larger test file (1MB)
    const largeContent = 'A'.repeat(1024 * 1024); // 1MB of 'A's
    fs.writeFileSync(path.join(this.tempDir, 'large-test.txt'), largeContent);

    console.log('✅ Test files created');
  }

  /**
   * Clean up temporary files
   */
  cleanupTestFiles() {
    console.log('🧹 Cleaning up test files...');
    if (fs.existsSync(this.tempDir)) {
      fs.rmSync(this.tempDir, { recursive: true, force: true });
    }

    // Clean up downloaded files
    const downloadDir = './test-downloads';
    if (fs.existsSync(downloadDir)) {
      fs.rmSync(downloadDir, { recursive: true, force: true });
    }
    console.log('✅ Cleanup completed');
  }

  /**
   * Test connection to Minio server
   */
  async testConnection() {
    console.log('\n🔌 Testing Minio connection...');
    try {
      const isConnected = await this.minio.testConnection();
      if (isConnected) {
        console.log('✅ Connection test passed');
        return true;
      } else {
        console.log('❌ Connection test failed');
        return false;
      }
    } catch (error) {
      console.error('❌ Connection test error:', error.message);
      return false;
    }
  }

  /**
   * Test bucket operations
   */
  async testBucketOperations() {
    console.log('\n🪣 Testing bucket operations...');
    try {
      await this.minio.ensureBucket(this.testBucket);
      console.log('✅ Bucket operations test passed');
      return true;
    } catch (error) {
      console.error('❌ Bucket operations test failed:', error.message);
      return false;
    }
  }

  /**
   * Test single file upload
   */
  async testSingleFileUpload() {
    console.log('\n📤 Testing single file upload...');
    try {
      const testFile = path.join(this.tempDir, 'test.txt');
      const objectName = `${this.testFolder}/test.txt`;
      
      const result = await this.minio.uploadFile(
        this.testBucket, 
        objectName, 
        testFile,
        { 'test-type': 'single-upload', 'description': 'Test file upload' }
      );

      if (result.success) {
        console.log('✅ Single file upload test passed');
        return true;
      } else {
        console.log('❌ Single file upload test failed');
        return false;
      }
    } catch (error) {
      console.error('❌ Single file upload test failed:', error.message);
      return false;
    }
  }

  /**
   * Test multiple files upload
   */
  async testMultipleFilesUpload() {
    console.log('\n📤📤 Testing multiple files upload...');
    try {
      const files = [
        { filePath: path.join(this.tempDir, 'test.json'), objectName: 'test.json' },
        { filePath: path.join(this.tempDir, 'large-test.txt'), objectName: 'large-test.txt' }
      ];

      const results = await this.minio.uploadMultipleFiles(this.testBucket, files, this.testFolder);
      
      const successful = results.filter(r => r.success).length;
      if (successful === files.length) {
        console.log('✅ Multiple files upload test passed');
        return true;
      } else {
        console.log('❌ Multiple files upload test failed');
        return false;
      }
    } catch (error) {
      console.error('❌ Multiple files upload test failed:', error.message);
      return false;
    }
  }

  /**
   * Test listing objects
   */
  async testListObjects() {
    console.log('\n📋 Testing list objects...');
    try {
      const objects = await this.minio.listObjects(this.testBucket, this.testFolder);
      
      if (objects.length > 0) {
        console.log(`📋 Found ${objects.length} objects:`);
        objects.forEach(obj => {
          console.log(`  - ${obj.name} (${(obj.size / 1024).toFixed(1)} KB)`);
        });
        console.log('✅ List objects test passed');
        return true;
      } else {
        console.log('❌ List objects test failed - no objects found');
        return false;
      }
    } catch (error) {
      console.error('❌ List objects test failed:', error.message);
      return false;
    }
  }

  /**
   * Test getting object metadata
   */
  async testGetMetadata() {
    console.log('\n📋 Testing get object metadata...');
    try {
      const objectName = `${this.testFolder}/test.txt`;
      const metadata = await this.minio.getObjectMetadata(this.testBucket, objectName);
      
      console.log('📋 Object metadata:');
      console.log(`  - Size: ${metadata.size} bytes`);
      console.log(`  - Last Modified: ${metadata.lastModified}`);
      console.log(`  - ETag: ${metadata.etag}`);
      console.log(`  - Custom metadata:`, metadata.metadata);
      
      console.log('✅ Get metadata test passed');
      return true;
    } catch (error) {
      console.error('❌ Get metadata test failed:', error.message);
      return false;
    }
  }

  /**
   * Test presigned URL generation
   */
  async testPresignedUrl() {
    console.log('\n🔗 Testing presigned URL generation...');
    try {
      const objectName = `${this.testFolder}/test.txt`;
      const url = await this.minio.getPresignedUrl(this.testBucket, objectName, 3600);
      
      console.log(`🔗 Presigned URL: ${url.substring(0, 100)}...`);
      console.log('✅ Presigned URL test passed');
      return true;
    } catch (error) {
      console.error('❌ Presigned URL test failed:', error.message);
      return false;
    }
  }

  /**
   * Test single file download
   */
  async testSingleFileDownload() {
    console.log('\n📥 Testing single file download...');
    try {
      const objectName = `${this.testFolder}/test.json`;
      const downloadPath = './test-downloads/downloaded-test.json';
      
      const result = await this.minio.downloadFile(this.testBucket, objectName, downloadPath);
      
      if (result.success && fs.existsSync(downloadPath)) {
        // Verify file content
        const content = fs.readFileSync(downloadPath, 'utf-8');
        const jsonData = JSON.parse(content);
        
        if (jsonData.testData === 'Hello Minio') {
          console.log('✅ Single file download test passed');
          return true;
        } else {
          console.log('❌ Downloaded file content verification failed');
          return false;
        }
      } else {
        console.log('❌ Single file download test failed');
        return false;
      }
    } catch (error) {
      console.error('❌ Single file download test failed:', error.message);
      return false;
    }
  }

  /**
   * Test downloading video files from the downloads folder
   */
  async testVideoFileOperations() {
    console.log('\n🎬 Testing video file operations...');
    try {
      // Look for an existing video file in the downloads folder
      const downloadsDir = './downloads';
      if (!fs.existsSync(downloadsDir)) {
        console.log('ℹ️  No downloads folder found, skipping video file test');
        return true;
      }

      const videoFiles = fs.readdirSync(downloadsDir)
        .filter(file => file.endsWith('.mp4'))
        .slice(0, 2); // Test with first 2 video files

      if (videoFiles.length === 0) {
        console.log('ℹ️  No video files found, skipping video file test');
        return true;
      }

      console.log(`🎬 Found ${videoFiles.length} video files to test with`);

      const videoBucket = 'ai-maker-videos';
      await this.minio.ensureBucket(videoBucket);

      // Upload a video file
      const videoFile = videoFiles[0];
      const videoPath = path.join(downloadsDir, videoFile);
      const objectName = `videos/${videoFile}`;

      console.log(`📤 Uploading video: ${videoFile}`);
      const uploadResult = await this.minio.uploadFile(
        videoBucket,
        objectName,
        videoPath,
        { 'content-type': 'video/mp4', 'source': 'youtube-download' }
      );

      if (!uploadResult.success) {
        console.log('❌ Video upload failed');
        return false;
      }

      // List videos in bucket
      const videoObjects = await this.minio.listObjects(videoBucket, 'videos/');
      console.log(`📋 Videos in bucket: ${videoObjects.length}`);

      // Download video to a different location
      const downloadPath = `./test-downloads/downloaded-${videoFile}`;
      const downloadResult = await this.minio.downloadFile(videoBucket, objectName, downloadPath);

      if (downloadResult.success && fs.existsSync(downloadPath)) {
        const originalSize = fs.statSync(videoPath).size;
        const downloadedSize = fs.statSync(downloadPath).size;
        
        if (originalSize === downloadedSize) {
          console.log('✅ Video file operations test passed');
          return true;
        } else {
          console.log(`❌ File size mismatch: original ${originalSize}, downloaded ${downloadedSize}`);
          return false;
        }
      } else {
        console.log('❌ Video download failed');
        return false;
      }

    } catch (error) {
      console.error('❌ Video file operations test failed:', error.message);
      return false;
    }
  }

  /**
   * Test object deletion
   */
  async testObjectDeletion() {
    console.log('\n🗑️  Testing object deletion...');
    try {
      const objectName = `${this.testFolder}/test.txt`;
      const success = await this.minio.deleteObject(this.testBucket, objectName);
      
      if (success) {
        console.log('✅ Object deletion test passed');
        return true;
      } else {
        console.log('❌ Object deletion test failed');
        return false;
      }
    } catch (error) {
      console.error('❌ Object deletion test failed:', error.message);
      return false;
    }
  }

  /**
   * Run all tests
   */
  async runAllTests() {
    console.log('🧪 Starting Minio Service Test Suite');
    console.log('=====================================\n');

    // Print configuration
    console.log('📋 Configuration:');
    console.log(`  - Endpoint: ${this.minioConfig.endPoint}:${this.minioConfig.port}`);
    console.log(`  - SSL: ${this.minioConfig.useSSL}`);
    console.log(`  - Access Key: ${this.minioConfig.accessKey}`);
    console.log(`  - Region: ${this.minioConfig.region}`);
    console.log(`  - Test Bucket: ${this.testBucket}`);
    console.log(`  - Test Folder: ${this.testFolder}`);
    console.log(`  - Source: ${process.env.MINIO_ENDPOINT ? '.env file' : 'defaults'}`);

    const results = [];

    try {
      // Setup
      await this.createTestFiles();

      // Run tests
      results.push({ name: 'Connection', passed: await this.testConnection() });
      results.push({ name: 'Bucket Operations', passed: await this.testBucketOperations() });
      results.push({ name: 'Single File Upload', passed: await this.testSingleFileUpload() });
      results.push({ name: 'Multiple Files Upload', passed: await this.testMultipleFilesUpload() });
      results.push({ name: 'List Objects', passed: await this.testListObjects() });
      results.push({ name: 'Get Metadata', passed: await this.testGetMetadata() });
      results.push({ name: 'Presigned URL', passed: await this.testPresignedUrl() });
      results.push({ name: 'Single File Download', passed: await this.testSingleFileDownload() });
      results.push({ name: 'Video File Operations', passed: await this.testVideoFileOperations() });
      results.push({ name: 'Object Deletion', passed: await this.testObjectDeletion() });

    } catch (error) {
      console.error('❌ Test suite error:', error.message);
    } finally {
      // Cleanup
      this.cleanupTestFiles();
    }

    // Print summary
    console.log('\n📊 Test Results Summary');
    console.log('========================');
    
    const passed = results.filter(r => r.passed).length;
    const total = results.length;

    results.forEach(result => {
      const status = result.passed ? '✅' : '❌';
      console.log(`${status} ${result.name}`);
    });

    console.log(`\n🎯 Overall: ${passed}/${total} tests passed`);

    if (passed === total) {
      console.log('🎉 All tests passed! Minio service is working correctly.');
    } else {
      console.log('⚠️  Some tests failed. Please check the Minio configuration and server status.');
    }

    return { passed, total, results };
  }
}

// Run tests if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  const tester = new MinioServiceTest();
  
  // Handle command line arguments
  const args = process.argv.slice(2);
  
  if (args.includes('--help')) {
    console.log(`
🧪 Minio Service Test Suite

Usage:
  node minio-test.js                    Run all tests
  node minio-test.js --help             Show this help

Configuration:
The test reads configuration from environment variables in .env file:
  - MINIO_ENDPOINT (e.g., 'nvda:30090' or 'localhost:9000')
  - MINIO_ACCESS_KEY
  - MINIO_SECRET_KEY
  - MINIO_SECURE (true/false)
  - MINIO_REGION (e.g., 'us-east-1')
  - MINIO_BUCKET (bucket to use for testing)

If .env variables are not found, defaults to localhost:9000 with minioadmin credentials.

Current .env configuration:
  - Endpoint: ${process.env.MINIO_ENDPOINT || 'not set (using localhost:9000)'}
  - Access Key: ${process.env.MINIO_ACCESS_KEY || 'not set (using minioadmin)'}
  - Bucket: ${process.env.MINIO_BUCKET || 'not set (using ai-maker-test)'}
  - Secure: ${process.env.MINIO_SECURE || 'not set (using false)'}

To start Minio server with Docker (if testing locally):
  docker run -p 9000:9000 -p 9001:9001 \\
    -e "MINIO_ROOT_USER=minioadmin" \\
    -e "MINIO_ROOT_PASSWORD=minioadmin" \\
    minio/minio server /data --console-address ":9001"
`);
    process.exit(0);
  }

  tester.runAllTests()
    .then(results => {
      process.exit(results.passed === results.total ? 0 : 1);
    })
    .catch(error => {
      console.error('💥 Test suite crashed:', error.message);
      process.exit(1);
    });
}

export default MinioServiceTest;
