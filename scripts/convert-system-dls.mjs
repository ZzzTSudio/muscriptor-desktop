import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { SoundBankLoader } from 'spessasynth_core'

const source = process.argv[2] ?? 'C:\\Windows\\System32\\drivers\\gm.dls'
const destination = resolve(process.argv[3] ?? 'runtime-assets/soundfonts/WindowsGM.sf2')
const bytes = await readFile(source)
const arrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
const bank = SoundBankLoader.fromArrayBuffer(arrayBuffer)
const sf2 = bank.writeSF2()
await mkdir(dirname(destination), { recursive: true })
await writeFile(destination, new Uint8Array(sf2))
bank.destroySoundBank()
console.log(`Converted ${source} -> ${destination}`)
