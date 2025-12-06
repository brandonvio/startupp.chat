import { google } from "googleapis";
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";
import dotenv from "dotenv";
import { MinioService } from "./minio-service.js";

// Load environment variables
dotenv.config();

const API_KEY = process.env.YT_API_KEY;

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

// CLI arguments
const INPUT = process.argv[2];
const DAYS = process.argv[3] ? parseInt(process.argv[3], 10) : null;

if (!INPUT) {
  console.error("❌ Error: Please provide a channel handle or playlist ID");
  console.log("Usage: node playlist.js <@channelname|playlist-id> [days]");
  console.log("Examples:");
  console.log("  node playlist.js @IBMTechnology                    # Get all videos from channel");
  console.log("  node playlist.js @IBMTechnology 90                 # Get videos from channel (last 90 days)");
  console.log("  node playlist.js PLn5MTSAqaf8pRCtt0x-Aqg7ZN4Sp0orKD # Get all videos from playlist");
  process.exit(1);
}

// Detect if input is a playlist ID or channel handle
function isPlaylistId(input) {
  return input.match(/^PL[a-zA-Z0-9_-]{32}$/) || input.match(/^UU[a-zA-Z0-9_-]{22}$/) || input.match(/^FL[a-zA-Z0-9_-]{22}$/);
}

const IS_PLAYLIST = isPlaylistId(INPUT);
const CHANNEL_HANDLE = IS_PLAYLIST ? null : INPUT;

if (process.argv[3] && isNaN(DAYS)) {
  console.error("❌ Error: Days parameter must be a valid number");
  console.log("Usage: node playlist.js <@channelname|playlist-id> [days]");
  process.exit(1);
}

const youtube = google.youtube({
  version: "v3",
  auth: API_KEY,
});

async function getChannelId(handle) {
  const res = await youtube.channels.list({
    part: "id",
    forHandle: handle,
  });

  if (!res.data.items?.length) {
    throw new Error("Channel not found");
  }

  return res.data.items[0].id;
}

async function getRecentVideoIds(channelId, days = null) {
  let videoIds = [];
  let nextPageToken;

  const searchParams = {
    part: "id",
    channelId,
    maxResults: 50,
    order: "date",
    type: "video",
    pageToken: nextPageToken,
  };

  // Only add publishedAfter filter if days is specified
  if (days !== null) {
    const cutoffDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    searchParams.publishedAfter = cutoffDate.toISOString();
  }

  do {
    searchParams.pageToken = nextPageToken;
    
    const res = await youtube.search.list(searchParams);

    if (res.data.items) {
      videoIds.push(...res.data.items.map((item) => item.id.videoId));
    }

    nextPageToken = res.data.nextPageToken;
  } while (nextPageToken);

  return videoIds;
}

async function getPlaylistVideoIds(playlistId, days = null) {
  let videoIds = [];
  let nextPageToken;

  do {
    const res = await youtube.playlistItems.list({
      part: "snippet",
      playlistId,
      maxResults: 50,
      pageToken: nextPageToken,
    });

    if (res.data.items) {
      let items = res.data.items;
      
      // Filter by date if days parameter is specified
      if (days !== null) {
        const cutoffDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
        items = items.filter(item => {
          const publishedAt = new Date(item.snippet.publishedAt);
          return publishedAt >= cutoffDate;
        });
      }
      
      videoIds.push(...items.map((item) => item.snippet.resourceId.videoId));
    }

    nextPageToken = res.data.nextPageToken;
  } while (nextPageToken);

  return videoIds;
}

async function getVideoDetails(videoIds) {
  const videos = [];

  for (let i = 0; i < videoIds.length; i += 50) {
    const res = await youtube.videos.list({
      part: "snippet,statistics,contentDetails",
      id: videoIds.slice(i, i + 50).join(","),
    });

    videos.push(
      ...res.data.items.map((video) => ({
        id: video.id,
        title: video.snippet.title,
        description: video.snippet.description,
        publishedAt: video.snippet.publishedAt,
        channelTitle: video.snippet.channelTitle,
        tags: video.snippet.tags || [],
        categoryId: video.snippet.categoryId,
        duration: video.contentDetails.duration,
        viewCount: parseInt(video.statistics.viewCount) || 0,
        likeCount: parseInt(video.statistics.likeCount) || 0,
        commentCount: parseInt(video.statistics.commentCount) || 0,
        thumbnails: video.snippet.thumbnails,
        url: `https://www.youtube.com/watch?v=${video.id}`,
      }))
    );
  }

  return videos;
}

async function checkPlaylistExistsInMinio(filename) {
  try {
    const objectName = `playlists/${filename}`;
    const metadata = await minioService.getObjectMetadata(BUCKET_NAME, objectName);
    return {
      exists: true,
      lastModified: metadata.lastModified,
      size: metadata.size,
      objectName
    };
  } catch (error) {
    if (error.code === 'NotFound' || error.code === 'NoSuchKey' || error.message.includes('Not Found')) {
      return { exists: false };
    }
    throw error; // Re-throw unexpected errors
  }
}

(async () => {
  try {
    // Test Minio connection
    console.log('🔧 Testing Minio connection...');
    const isMinioConnected = await minioService.testConnection();
    if (!isMinioConnected) {
      console.log('⚠️  Warning: Minio connection failed. Playlist will only be saved locally.');
    }

    let channelId = null;
    let ids = [];
    
    if (IS_PLAYLIST) {
      console.log(`🎵 Fetching videos from playlist ${INPUT}...`);
      if (DAYS !== null) {
        console.log(`📅 Filtering videos from last ${DAYS} days...`);
      } else {
        console.log(`📅 Fetching all videos from playlist...`);
      }
      ids = await getPlaylistVideoIds(INPUT, DAYS);
    } else {
      console.log(`🔍 Fetching channel information for ${CHANNEL_HANDLE}...`);
      channelId = await getChannelId(CHANNEL_HANDLE);

      if (DAYS !== null) {
        console.log(`📅 Fetching videos from last ${DAYS} days...`);
      } else {
        console.log(`📅 Fetching all videos from channel...`);
      }
      ids = await getRecentVideoIds(channelId, DAYS);
    }

    console.log(`📝 Fetching detailed information for ${ids.length} videos...`);
    const videos = await getVideoDetails(ids);

    // Create playlists directory if it doesn't exist
    mkdirSync("playlists", { recursive: true });

    // Generate filename based on input type
    const filename = IS_PLAYLIST 
      ? `playlist-${INPUT.toLowerCase()}.json`
      : CHANNEL_HANDLE.replace("@", "").toLowerCase() + `.json`;
    const filepath = join("playlists", filename);

    // Check if playlist already exists in Minio
    if (isMinioConnected) {
      console.log('🔍 Checking if playlist already exists in Minio...');
      const existsInfo = await checkPlaylistExistsInMinio(filename);
      
      if (existsInfo.exists) {
        const lastModified = new Date(existsInfo.lastModified).toLocaleString();
        console.log(`⏭️  Playlist already exists in Minio: playlists/${filename}`);
        console.log(`📅 Last modified: ${lastModified}`);
        console.log(`📁 Size: ${(existsInfo.size / 1024).toFixed(1)} KB`);
        
        // Ask if user wants to proceed anyway
        console.log('💡 To update the playlist, continue with the fetch...');
      } else {
        console.log(`📭 Playlist not found in Minio - will upload after creation`);
      }
    }

    const playlistData = {
      totalVideos: videos.length,
      fetchedAt: new Date().toISOString(),
      videos: videos,
    };

    // Add source-specific metadata
    if (IS_PLAYLIST) {
      playlistData.playlistId = INPUT;
      playlistData.sourceType = 'playlist';
    } else {
      playlistData.channelHandle = CHANNEL_HANDLE;
      playlistData.channelId = channelId;
      playlistData.sourceType = 'channel';
    }

    // Only include days in the data if it was specified
    if (DAYS !== null) {
      playlistData.days = DAYS;
    }

    // Save to local file
    writeFileSync(filepath, JSON.stringify(playlistData, null, 2), "utf-8");
    
    const timeframe = DAYS !== null ? ` (last ${DAYS} days)` : ' (all videos)';
    console.log(`✅ Saved ${videos.length} videos${timeframe} to ${filepath}`);

    // Upload to Minio if connected
    if (isMinioConnected) {
      try {
        console.log('📤 Uploading playlist to Minio...');
        
        const objectName = `playlists/${filename}`;
        const metadata = {
          'total-videos': String(videos.length),
          'fetched-at': playlistData.fetchedAt,
          'file-type': 'playlist',
          'source-type': playlistData.sourceType,
          ...(DAYS !== null && { 'days-filter': String(DAYS) })
        };

        // Add source-specific metadata
        if (IS_PLAYLIST) {
          metadata['playlist-id'] = INPUT;
        } else {
          metadata['channel-handle'] = CHANNEL_HANDLE;
          metadata['channel-id'] = channelId;
        }

        const uploadResult = await minioService.uploadFile(
          BUCKET_NAME,
          objectName,
          filepath,
          metadata
        );
        
        console.log(`☁️  Successfully uploaded playlist to Minio: ${BUCKET_NAME}/${objectName}`);
        console.log(`📋 ETag: ${uploadResult.etag}`);
        
        // Clean up local file after successful upload (optional)
        // fs.unlinkSync(filepath);
        // console.log('🧹 Cleaned up local file after Minio upload');
        
      } catch (uploadError) {
        console.error('❌ Failed to upload playlist to Minio:', uploadError.message);
        console.log('📁 Playlist remains available locally due to upload failure');
      }
    }

  } catch (err) {
    console.error("❌ Error:", err.message);
  }
})();
