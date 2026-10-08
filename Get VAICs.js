import fs from 'fs'
import { exec } from 'child_process'
import util from 'util'

let j = JSON.parse(fs.readFileSync(`AllDYUserVAICs - 认知醒悟社.json`).toString())
j = j

let execAsync = util.promisify(exec);

async function downloadAll(items, concurrency = 5) {
    let index = 0;

    // Ensure output directory exists
    await execAsync('mkdir -p Audios');

    async function worker() {
        while (index < items.length) {
            let currentIndex = index++;
            let a = items[currentIndex];
            /* let url = a.music.play_url.url_list[0];
            let dest = `Audios/${a.aweme_id}.mp3`;

            let cmd = `wget -O "${dest}" "${url}"`; */

            /* let url = a.video.play_addr.url_list[1];
            let dest = `Videos/${a.aweme_id}.mp4`;

            let cmd = `wget -O "${dest}" "${url}"`; */
            try {
                console.log(`[Start] Downloading ${a.aweme_id}`);
                await execAsync(cmd);
                console.log(`[Done] ${a.aweme_id}`);
            } catch (err) {
                console.error(`[Error] Failed ${a.aweme_id}:`, err.message);
            }
        }
    }

    // Spawn worker pool
    let workers = Array(concurrency).fill(null).map(() => worker());
    await Promise.all(workers);
    console.log("All downloads complete!");
}

// Run it:
downloadAll(j, 5);