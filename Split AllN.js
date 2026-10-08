import fs from 'fs'
let allN = JSON.parse(fs.readFileSync(`AllN - Load DYUser Page and scroll to load all VAICs.json`).toString())
let n = Math.floor(allN.length / 2)
fs.writeFileSync(`AllN - Load DYUser Page and scroll to load all VAICs P1.json`, JSON.stringify(allN.slice(0, n), null, 1))
fs.writeFileSync(`AllN - Load DYUser Page and scroll to load all VAICs P2.json`, JSON.stringify(allN.slice(n), null, 1))