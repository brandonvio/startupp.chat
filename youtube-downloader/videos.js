import fetch from 'node-fetch';
import { writeFileSync } from 'fs';

const API_KEY = "AIzaSyC5Q-3FRIn6F6vVqIaxn_KeTVimt3QyLZc"; // Replace with your YouTube Data API v3 key
const CHANNEL_HANDLE = '@aiDotEngineer';

async function getChannelId(handle) {
  // Try with forHandle first (remove @ symbol if present)
  const cleanHandle = handle.replace('@', '');
  let url = `https://www.googleapis.com/youtube/v3/channels?part=id&forHandle=${cleanHandle}&key=${API_KEY}`;
  let data = await fetch(url).then(res => res.json());

  // Check for API errors first
  if (data.error) {
    if (data.error.code === 403 && data.error.message.includes('YouTube Data API v3 has not been used')) {
      throw new Error(`YouTube Data API v3 is not enabled for your project. Please enable it at: ${data.error.details[0]['@type'] ? data.error.details.find(d => d['@type'] === 'type.googleapis.com/google.rpc.Help')?.links[0]?.url || 'https://console.developers.google.com/apis/api/youtube.googleapis.com/overview' : 'https://console.developers.google.com/apis/api/youtube.googleapis.com/overview'}`);
    } else if (data.error.code === 400 && data.error.message.includes('API key not valid')) {
      throw new Error('Invalid API key. Please check your YouTube Data API v3 key.');
    } else {
      throw new Error(`YouTube API Error (${data.error.code}): ${data.error.message}`);
    }
  }

  // If forHandle doesn't work, try forUsername
  if (!data.items || !data.items[0]) {
    url = `https://www.googleapis.com/youtube/v3/channels?part=id&forUsername=${cleanHandle}&key=${API_KEY}`;
    data = await fetch(url).then(res => res.json());
    
    if (data.error) {
      throw new Error(`YouTube API Error (${data.error.code}): ${data.error.message}`);
    }
  }

  // If still no results, try searching by channel name
  if (!data.items || !data.items[0]) {
    url = `https://www.googleapis.com/youtube/v3/search?part=id&type=channel&q=${encodeURIComponent(cleanHandle)}&key=${API_KEY}`;
    data = await fetch(url).then(res => res.json());
    
    if (data.error) {
      throw new Error(`YouTube API Error (${data.error.code}): ${data.error.message}`);
    }
    
    if (data.items && data.items[0] && data.items[0].id.channelId) {
      return data.items[0].id.channelId;
    }
  }

  if (!data.items || !data.items[0]) {
    throw new Error(`Channel not found for handle: ${handle}. Please check the channel handle is correct.`);
  }
  
  return data.items[0].id;
}

async function getUploadsPlaylistId(channelId) {
  const url = `https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id=${channelId}&key=${API_KEY}`;
  const data = await fetch(url).then(res => res.json());
  return data.items[0].contentDetails.relatedPlaylists.uploads;
}

async function getAllVideoIds(playlistId) {
  let videoIds = [];
  let pageToken = '';
  do {
    const url = `https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId=${playlistId}&maxResults=50&pageToken=${pageToken}&key=${API_KEY}`;
    const data = await fetch(url).then(res => res.json());

    videoIds.push(...data.items.map(item => item.contentDetails.videoId));
    pageToken = data.nextPageToken || '';
  } while (pageToken);

  return videoIds;
}

(async () => {
  try {
    const channelId = await getChannelId(CHANNEL_HANDLE);
    const uploadsPlaylistId = await getUploadsPlaylistId(channelId);
    const ids = await getAllVideoIds(uploadsPlaylistId);

    writeFileSync('videos.txt', ids.join('\n'), 'utf-8');
    console.log(`✅ Saved ${ids.length} video IDs to videos.txt`);
  } catch (err) {
    console.error('❌ Error:', err.message);
  }
})();
