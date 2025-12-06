import ytdl from '@distube/ytdl-core';
import fs from 'fs';
import path from 'path';
import dotenv from 'dotenv';
import { MinioService } from './minio-service.js';

// Load environment variables
dotenv.config();

// Configuration
const OUTPUT_DIR = './downloads';
const QUALITY = 'highest'; // Options: 'highest', 'lowest', 'highestaudio', 'lowestaudio'

// Initialize Minio service
function parseMinioEndpoint(endpoint) {
  if (!endpoint) return { endPoint: 'localhost', port: 9000 };
  
  // Check if endpoint contains port
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

const BUCKET_NAME = process.env.MINIO_BUCKET || 'videos';

/**
 * Download a YouTube video by its ID
 * @param {string} videoId - The YouTube video ID
 * @param {string} outputDir - Directory to save the video (optional)
 * @param {string} quality - Video quality preference (optional)
 * @returns {Promise<string>} - Path to the downloaded file
 */
async function downloadVideo(videoId, outputDir = OUTPUT_DIR, quality = QUALITY) {
  try {
    // Validate video ID
    if (!videoId || typeof videoId !== 'string') {
      throw new Error('Valid video ID is required');
    }

    // Ensure output directory exists
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // Check if files already exist in Minio storage
    const fileExtension = (quality === 'highestaudio' || quality === 'lowestaudio') ? 'mp3' : 'mp4';
    const filename = `${videoId}.${fileExtension}`;
    const filepath = path.join(outputDir, filename);
    const metadataFilename = `${videoId}.json`;
    const metadataFilepath = path.join(outputDir, metadataFilename);

    // Check Minio storage first
    console.log('🔍 Checking if files exist in Minio storage...');
    try {
      const videoObjectName = `downloads/${filename}`;
      const metadataObjectName = `downloads/${metadataFilename}`;
      
      const [videoExists, metadataExists] = await Promise.allSettled([
        minioService.getObjectMetadata(BUCKET_NAME, videoObjectName),
        minioService.getObjectMetadata(BUCKET_NAME, metadataObjectName)
      ]);

      const videoExistsInMinio = videoExists.status === 'fulfilled';
      const metadataExistsInMinio = metadataExists.status === 'fulfilled';

      if (videoExistsInMinio && metadataExistsInMinio) {
        console.log(`⏭️  Skipping ${videoId} - files already exist in Minio storage`);
        console.log(`☁️  Video: ${BUCKET_NAME}/${videoObjectName} (${(videoExists.value.size / 1024 / 1024).toFixed(1)} MB)`);
        console.log(`☁️  Metadata: ${BUCKET_NAME}/${metadataObjectName}`);
        
        return {
          skipped: true,
          alreadyExistsInMinio: true,
          videoObjectName,
          metadataObjectName
        };
      }

      // If only some files exist in Minio, log what's missing
      if (videoExistsInMinio && !metadataExistsInMinio) {
        console.log(`🎬 Video exists in Minio but metadata missing for ${videoId}`);
      } else if (!videoExistsInMinio && metadataExistsInMinio) {
        console.log(`📄 Metadata exists in Minio but video missing for ${videoId}`);
      } else {
        console.log(`📭 No files found in Minio for ${videoId} - proceeding with download`);
      }

    } catch (error) {
      // Only show errors for actual connection/service issues, not "not found"
      if (!error.message.includes('Not Found') && !error.message.includes('NoSuchKey')) {
        console.log(`⚠️  Could not check Minio storage (${error.message}) - proceeding with download`);
      } else {
        console.log(`📭 No files found in Minio for ${videoId} - proceeding with download`);
      }
    }

    // Create temporary local paths for download and upload
    const tempFilepath = path.join(outputDir, filename);
    const tempMetadataFilepath = path.join(outputDir, metadataFilename);

    // Construct YouTube URL
    const url = `https://www.youtube.com/watch?v=${videoId}`;

    // Check if URL is valid
    if (!ytdl.validateURL(url)) {
      throw new Error(`Invalid YouTube URL: ${url}`);
    }

    // Get video info with retry logic
    console.log('📋 Getting video information...');
    let info;
    try {
      info = await ytdl.getInfo(url, {
        requestOptions: {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
          }
        }
      });
    } catch (infoError) {
      console.error('❌ Failed to get video info:', infoError.message);
      throw new Error(`Cannot access video ${videoId}. It may be private, deleted, or region-locked.`);
    }

    const title = info.videoDetails.title.replace(/[^\w\s-]/g, '').replace(/\s+/g, ' ').trim();
    const author = info.videoDetails.author.name;
    const duration = info.videoDetails.lengthSeconds;
    
    console.log(`📺 Title: ${title}`);
    console.log(`👤 Author: ${author}`);
    console.log(`⏱️  Duration: ${Math.floor(duration / 60)}:${(duration % 60).toString().padStart(2, '0')}`);

    // Determine file format and quality
    let format;
    
    if (quality === 'highestaudio' || quality === 'lowestaudio') {
      format = ytdl.chooseFormat(info.formats, { quality: quality });
      // fileExtension already determined earlier
    } else {
      format = ytdl.chooseFormat(info.formats, { 
        quality: quality,
        filter: 'audioandvideo'
      });
      
      // Fallback to video-only if no combined format available
      if (!format) {
        format = ytdl.chooseFormat(info.formats, { 
          quality: quality,
          filter: 'videoonly'
        });
      }
    }

    if (!format) {
      throw new Error('No suitable format found for download');
    }

    console.log(`🎬 Selected format: ${format.qualityLabel || format.audioBitrate + 'kbps'} (${format.container})`);

    // Create filename using video ID (reuse variables from earlier check)
    // filename, tempFilepath, metadataFilename, tempMetadataFilepath already defined above
    
    // Save metadata to JSON file (always create temporarily)
    const metadata = {
      videoId: videoId,
      url: url,
      title: info.videoDetails.title,
      author: info.videoDetails.author,
      description: info.videoDetails.description,
      lengthSeconds: info.videoDetails.lengthSeconds,
      viewCount: info.videoDetails.viewCount,
      publishDate: info.videoDetails.publishDate,
      uploadDate: info.videoDetails.uploadDate,
      category: info.videoDetails.category,
      keywords: info.videoDetails.keywords,
      thumbnails: info.videoDetails.thumbnails,
      formats: info.formats,
      selectedFormat: format,
      downloadDate: new Date().toISOString(),
      filename: filename
    };

    fs.writeFileSync(tempMetadataFilepath, JSON.stringify(metadata, null, 2));
    console.log(`📄 Metadata saved temporarily: ${tempMetadataFilepath}`);

    // Download video
    console.log('⬇️  Starting download...');
    const stream = ytdl(url, { 
      format: format,
      requestOptions: {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
      }
    });
    const writeStream = fs.createWriteStream(tempFilepath);

    // Track download progress
    let downloadedBytes = 0;
    const totalBytes = parseInt(format.contentLength || '0');

    stream.on('data', (chunk) => {
      downloadedBytes += chunk.length;
      if (totalBytes > 0) {
        const progress = ((downloadedBytes / totalBytes) * 100).toFixed(1);
        process.stdout.write(`\r📊 Progress: ${progress}% (${(downloadedBytes / 1024 / 1024).toFixed(1)} MB)`);
      }
    });

    stream.on('error', (error) => {
      console.error('\n❌ Download error:', error.message);
      // Clean up partial file
      if (fs.existsSync(tempFilepath)) {
        fs.unlinkSync(tempFilepath);
      }
    });

    // Pipe the stream to file
    stream.pipe(writeStream);

    return new Promise(async (resolve, reject) => {
      writeStream.on('finish', async () => {
        console.log(`\n✅ Download completed: ${tempFilepath}`);
        console.log(`📁 File size: ${(fs.statSync(tempFilepath).size / 1024 / 1024).toFixed(1)} MB`);
        
        try {
          // Define object names for Minio upload
          const videoObjectName = `downloads/${filename}`;
          const metadataObjectName = `downloads/${metadataFilename}`;
          
          // Upload video file to Minio
          console.log('\n📤 Uploading video to Minio...');
          const videoUploadResult = await minioService.uploadFile(
            BUCKET_NAME,
            videoObjectName,
            tempFilepath,
            {
              'video-id': videoId,
              'title': info.videoDetails.title,
              'author': info.videoDetails.author.name,
              'duration': String(info.videoDetails.lengthSeconds),
              'original-filename': filename
            }
          );
          
          // Upload metadata file to Minio
          console.log('📤 Uploading metadata to Minio...');
          const metadataUploadResult = await minioService.uploadFile(
            BUCKET_NAME,
            metadataObjectName,
            tempMetadataFilepath,
            {
              'video-id': videoId,
              'file-type': 'metadata',
              'original-filename': metadataFilename
            }
          );
          
          console.log('✅ Successfully uploaded to Minio storage');
          
          // Clean up temporary files
          console.log('🧹 Cleaning up temporary files...');
          try {
            fs.unlinkSync(tempFilepath);
            fs.unlinkSync(tempMetadataFilepath);
            console.log('✅ Temporary files cleaned up');
          } catch (cleanupError) {
            console.warn('⚠️  Warning: Could not clean up temporary files:', cleanupError.message);
          }
          
          resolve({
            videoUpload: videoUploadResult,
            metadataUpload: metadataUploadResult,
            cleanedUp: true
          });
          
        } catch (uploadError) {
          console.error('❌ Failed to upload to Minio:', uploadError.message);
          console.log('📁 Files remain available locally due to upload failure');
          resolve({
            localPath: tempFilepath,
            uploadFailed: true,
            error: uploadError.message
          });
        }
      });

      writeStream.on('error', (error) => {
        console.error('\n❌ Write error:', error.message);
        reject(error);
      });
    });

  } catch (error) {
    console.error('❌ Error downloading video:', error.message);
    throw error;
  }
}

/**
 * Download multiple videos by their IDs
 * @param {string[]} videoIds - Array of YouTube video IDs
 * @param {string} outputDir - Directory to save videos (optional)
 * @param {string} quality - Video quality preference (optional)
 */
async function downloadMultipleVideos(videoIds, outputDir = OUTPUT_DIR, quality = QUALITY) {
  console.log(`🚀 Starting download of ${videoIds.length} videos...\n`);
  
  const results = [];
  let skipped = 0;
  let downloaded = 0;
  let failed = 0;

  for (let i = 0; i < videoIds.length; i++) {
    try {
      console.log(`\n📹 Video ${i + 1}/${videoIds.length}: ${videoIds[i]}`);
      const result = await downloadVideo(videoIds[i], outputDir, quality);
      
      if (result.skipped || result.alreadyExistsInMinio) {
        skipped++;
        results.push({ videoId: videoIds[i], result, success: true, skipped: true });
      } else if (result.cleanedUp || result.videoUpload) {
        downloaded++;
        results.push({ videoId: videoIds[i], result, success: true, downloaded: true });
      } else {
        downloaded++;
        results.push({ videoId: videoIds[i], result, success: true, downloaded: true });
      }
    } catch (error) {
      failed++;
      console.error(`❌ Failed to download video ${videoIds[i]}:`, error.message);
      results.push({ videoId: videoIds[i], error: error.message, success: false });
    }
  }

  // Enhanced summary
  console.log(`\n📊 Download Summary:`);
  console.log(`� Downloaded: ${downloaded}`);
  console.log(`⏭️  Skipped (already exists): ${skipped}`);
  console.log(`❌ Failed: ${failed}`);
  console.log(`📋 Total processed: ${videoIds.length}`);
  
  if (failed > 0) {
    console.log('\n❌ Failed downloads:');
    results.filter(r => !r.success).forEach(r => {
      console.log(`  - ${r.videoId}: ${r.error}`);
    });
  }

  return results;
}

/**
 * Read video IDs from a file and download them
 * Supports both JSON playlist files and plain text files
 */
async function downloadFromFile(filename = 'videos.txt') {
  try {
    let filepath = filename;
    
    // If filename doesn't include a path, check playlists folder first
    if (!filename.includes('/') && !filename.includes('\\')) {
      const playlistPath = path.join('playlists', filename);
      
      // Check if file exists in playlists folder
      if (fs.existsSync(playlistPath)) {
        filepath = playlistPath;
        console.log(`📁 Found playlist file: ${filepath}`);
      } else if (fs.existsSync(filename)) {
        filepath = filename;
        console.log(`📁 Found file in current directory: ${filepath}`);
      } else {
        throw new Error(`File not found: ${filename} (checked both current directory and playlists/ folder)`);
      }
    } else {
      // Full path provided, use as-is
      if (!fs.existsSync(filepath)) {
        throw new Error(`File ${filepath} not found`);
      }
    }

    const content = fs.readFileSync(filepath, 'utf-8');
    let videoIds = [];
    let playlistInfo = null;

    // Check if it's a JSON file
    if (filepath.endsWith('.json')) {
      try {
        const jsonData = JSON.parse(content);
        
        // Validate JSON structure
        if (!jsonData.videos || !Array.isArray(jsonData.videos)) {
          throw new Error('Invalid JSON structure: missing videos array');
        }
        
        videoIds = jsonData.videos.map(video => {
          if (typeof video === 'string') {
            return video; // Simple string array
          } else if (video.id) {
            return video.id; // Object with id property
          } else {
            throw new Error('Invalid video object: missing id property');
          }
        });
        
        playlistInfo = {
          channelHandle: jsonData.channelHandle,
          channelId: jsonData.channelId,
          totalVideos: jsonData.totalVideos,
          fetchedAt: jsonData.fetchedAt,
          days: jsonData.days
        };
        
        console.log(`📋 JSON Playlist Info:`);
        if (playlistInfo.channelHandle) console.log(`   Channel: ${playlistInfo.channelHandle}`);
        if (playlistInfo.fetchedAt) console.log(`   Fetched: ${new Date(playlistInfo.fetchedAt).toLocaleString()}`);
        if (playlistInfo.days) console.log(`   Period: Last ${playlistInfo.days} days`);
        
      } catch (jsonError) {
        throw new Error(`Failed to parse JSON file: ${jsonError.message}`);
      }
    } else {
      // Plain text file - each line is a video ID
      videoIds = content.split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0);
    }

    if (videoIds.length === 0) {
      throw new Error(`No video IDs found in ${filepath}`);
    }

    const fileType = filepath.endsWith('.json') ? 'JSON playlist' : 'text file';
    console.log(`📁 Found ${videoIds.length} video IDs in ${fileType}: ${filepath}`);
    
    const results = await downloadMultipleVideos(videoIds);
    
    // Show additional summary for JSON playlists
    if (playlistInfo) {
      console.log(`\n📊 Playlist Summary:`);
      console.log(`   Channel: ${playlistInfo.channelHandle || 'Unknown'}`);
      console.log(`   Total videos in playlist: ${playlistInfo.totalVideos || videoIds.length}`);
      if (results) {
        const downloaded = results.filter(r => r.success && r.downloaded).length;
        const skipped = results.filter(r => r.success && r.skipped).length;
        const failed = results.filter(r => !r.success).length;
        console.log(`   Downloaded: ${downloaded}, Skipped: ${skipped}, Failed: ${failed}`);
      }
    }

  } catch (error) {
    console.error('❌ Error reading from file:', error.message);
  }
}

// Command line interface
const args = process.argv.slice(2);

// Test Minio connection on startup
async function initializeServices() {
  console.log('🔧 Initializing services...');
  const isMinioConnected = await minioService.testConnection();
  if (!isMinioConnected) {
    console.log('⚠️  Warning: Minio connection failed. Files will only be saved locally.');
  }
  return isMinioConnected;
}

if (args.length === 0) {
  console.log(`
🎬 YouTube Video Downloader with Minio Storage

Usage:
  node download-video.js <video-id>              Download single video
  node download-video.js --file                  Download all videos from videos.txt
  node download-video.js --file <filename>       Download all videos from specified file
  node download-video.js <filename>              Download all videos from specified file (shorthand)
  node download-video.js --help                  Show this help

Examples:
  node download-video.js dQw4w9WgXcQ
  node download-video.js --file
  node download-video.js --file ibmtechnology.json
  node download-video.js ibmtechnology.json      (shorthand - same as above)
  node download-video.js playlists/markets.json
  node download-video.js --file videos.txt       (legacy text file support)

File Format Support:
  - JSON Playlist Files: Rich playlist files with video metadata (preferred)
    Example: ibmtechnology.json, markets.json
  - Text Files: Simple newline-separated video IDs (legacy support)
    Example: videos.txt

Features:
  - Downloads videos locally to ./downloads folder
  - Automatically uploads to Minio storage in /downloads folder
  - Saves metadata as JSON files
  - Supports bulk downloads from JSON playlists or text files
  - Smart file lookup: Checks playlists/ folder first, then current directory
  - Smart skip: Automatically skips files that already exist in Minio
  - Selective re-download: Downloads missing video or metadata files
  - Displays playlist information for JSON files

Quality options (set QUALITY in script):
  - highest: Best video quality
  - lowest: Lowest video quality  
  - highestaudio: Best audio only
  - lowestaudio: Lowest audio only

Minio Configuration:
  Configure Minio settings in .env file:
  - MINIO_ENDPOINT, MINIO_PORT, MINIO_ACCESS_KEY, etc.
`);
  process.exit(0);
}

// Parse command line arguments
if (args[0] === '--help') {
  console.log('Help message already shown above');
  process.exit(0);
} else if (args[0] === '--file') {
  const filename = args[1] || 'videos.txt';
  initializeServices().then(() => {
    downloadFromFile(filename);
  });
} else if (args[0] && (args[0].endsWith('.txt') || args[0].endsWith('.json'))) {
  // Shorthand for file download - if argument ends with .txt or .json, treat as filename
  const filename = args[0];
  initializeServices().then(() => {
    downloadFromFile(filename);
  });
} else {
  // Single video download
  const videoId = args[0];
  initializeServices().then(() => {
    downloadVideo(videoId)
      .then(result => {
        if (result.skipped || result.alreadyExistsInMinio) {
          console.log(`⏭️  Video ${videoId} already exists in Minio storage - skipped download`);
          console.log(`☁️  Video: ${result.videoObjectName}`);
          console.log(`☁️  Metadata: ${result.metadataObjectName}`);
        } else if (result.cleanedUp) {
          console.log(`🎉 Download, upload, and cleanup complete for ${videoId}!`);
          console.log(`☁️  Video: ${result.videoUpload.bucketName}/${result.videoUpload.objectName}`);
          console.log(`☁️  Metadata: ${result.metadataUpload.bucketName}/${result.metadataUpload.objectName}`);
        } else if (result.uploadFailed) {
          console.log(`⚠️  Download complete but upload failed for ${videoId}`);
          console.log(`📁 Local file: ${result.localPath}`);
        } else {
          console.log(`🎉 Download and upload complete for ${videoId}!`);
          if (result.videoUpload) {
            console.log(`☁️  Video: ${result.videoUpload.bucketName}/${result.videoUpload.objectName}`);
          }
        }
      })
      .catch(error => {
        console.error('💥 Download failed:', error.message);
        process.exit(1);
      });
  });
}
