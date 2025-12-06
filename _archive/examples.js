#!/usr/bin/env node

/**
 * Example usage of the YouTube video downloader
 * 
 * This script demonstrates different ways to use the download-video.js script
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Example video IDs for testing (these are public videos)
const EXAMPLE_VIDEOS = [
  'dQw4w9WgXcQ', // Rick Astley - Never Gonna Give You Up
  'L_jWHffIx5E', // Smash Mouth - All Star
];

async function runExample() {
  console.log('🎬 YouTube Video Downloader Examples\n');

  try {
    // Example 1: Download a single video
    console.log('📹 Example 1: Downloading a single video...');
    console.log('Command: node download-video.js dQw4w9WgXcQ\n');
    
    const { stdout: output1 } = await execAsync('node download-video.js dQw4w9WgXcQ');
    console.log(output1);

    // Example 2: Show help
    console.log('\n📖 Example 2: Showing help...');
    console.log('Command: node download-video.js --help\n');
    
    const { stdout: output2 } = await execAsync('node download-video.js --help');
    console.log(output2);

    // Example 3: Download from videos.txt file (if it exists)
    console.log('\n📁 Example 3: Downloading from videos.txt file...');
    console.log('Command: node download-video.js --file\n');
    
    try {
      const { stdout: output3 } = await execAsync('node download-video.js --file');
      console.log(output3);
    } catch (error) {
      console.log('Note: videos.txt file not found or empty. This is expected if you haven\'t run videos.js yet.');
    }

  } catch (error) {
    console.error('❌ Error running examples:', error.message);
  }
}

// Show usage examples
console.log(`
🎬 YouTube Video Downloader Usage Examples

1. Download a single video:
   node download-video.js <video-id>
   
   Example: node download-video.js dQw4w9WgXcQ

2. Download all videos from videos.txt:
   node download-video.js --file
   
3. Download videos from a custom file:
   node download-video.js --file <filename>
   
   Example: node download-video.js --file my-videos.txt

4. Show help:
   node download-video.js --help

Quality Settings (edit the script to change):
- highest: Best video quality (default)
- lowest: Lowest video quality
- highestaudio: Best audio only (saves as .mp3)
- lowestaudio: Lowest audio only (saves as .mp3)

Output Directory:
- Videos are saved to ./downloads by default
- The directory will be created automatically

Features:
✅ Progress tracking during download
✅ Error handling and recovery
✅ Batch downloading from file
✅ Automatic filename sanitization
✅ File size reporting
✅ Download summary for multiple videos

Example Video IDs for testing:
- dQw4w9WgXcQ (Rick Astley - Never Gonna Give You Up)
- L_jWHffIx5E (Smash Mouth - All Star)
`);

// If script is run directly, ask user if they want to run examples
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('\nWould you like to run the examples? (y/n)');
  
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (input) => {
    const answer = input.toString().trim().toLowerCase();
    if (answer === 'y' || answer === 'yes') {
      runExample();
    } else {
      console.log('👋 Examples skipped. Use the commands above to download videos!');
      process.exit(0);
    }
  });
}
