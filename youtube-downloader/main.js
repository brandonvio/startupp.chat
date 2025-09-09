const ytpl = require('ytpl');
const uploadsPlaylistId = 'PLcfpQ4tk2k0UMEJY1KzWu02OkvCc1e5og';

ytpl(uploadsPlaylistId, { pages: Infinity })
  .then(playlist => {
    const ids = playlist.items.map(item => item.id);
    console.log(ids);
  });
