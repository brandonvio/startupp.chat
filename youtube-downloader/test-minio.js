import dotenv from 'dotenv';
import { MinioService } from './minio-service.js';

// Load environment variables
dotenv.config();

// Parse endpoint and port
function parseMinioEndpoint(endpoint) {
  if (!endpoint) return { endPoint: 'localhost', port: 9000 };
  
  if (endpoint.includes(':')) {
    const [host, port] = endpoint.split(':');
    return {
      endPoint: host,
      port: parseInt(port) || 9000
    };
  }
  
  return {
    endPoint: endpoint,
    port: parseInt(process.env.MINIO_PORT) || 9000
  };
}

const { endPoint, port } = parseMinioEndpoint(process.env.MINIO_ENDPOINT);

console.log('🔧 Testing Minio configuration:');
console.log(`📍 Endpoint: ${endPoint}:${port}`);
console.log(`🔑 Access Key: ${process.env.MINIO_ACCESS_KEY}`);
console.log(`🔐 SSL: ${process.env.MINIO_SECURE === 'true'}`);
console.log(`🪣 Bucket: ${process.env.MINIO_BUCKET}`);

const minioService = new MinioService({
  endPoint,
  port,
  useSSL: process.env.MINIO_SECURE === 'true',
  accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
  secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin'
});

// Test connection
minioService.testConnection()
  .then(success => {
    if (success) {
      console.log('🎉 Minio connection test successful!');
      return minioService.ensureBucket(process.env.MINIO_BUCKET || 'videos');
    } else {
      console.log('❌ Minio connection test failed');
    }
  })
  .then(result => {
    if (result) {
      console.log('✅ Bucket verification successful');
    }
  })
  .catch(error => {
    console.error('💥 Error:', error.message);
  });
