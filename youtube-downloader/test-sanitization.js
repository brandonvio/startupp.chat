import dotenv from 'dotenv';
import { MinioService } from './minio-service.js';
import fs from 'fs';

dotenv.config();

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

const minioService = new MinioService({
  endPoint,
  port,
  useSSL: process.env.MINIO_SECURE === 'true',
  accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
  secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin'
});

// Test metadata sanitization
const testMetadata = {
  'title': 'Video with 特殊字符 and\nnewlines\tand\rtabs',
  'description': 'This has émojis 🎬 and other unicode chars ñ',
  'author': 'Channel@Name with symbols!',
  'normal-field': 'This should be fine'
};

console.log('🧪 Testing metadata sanitization:');
console.log('📥 Original metadata:', testMetadata);

const sanitized = minioService.sanitizeMetadata(testMetadata);
console.log('📤 Sanitized metadata:', sanitized);

console.log('\n✅ Metadata sanitization test completed');
