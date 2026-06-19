import SparkMD5 from 'spark-md5'

const CHUNK_SIZE = 4 * 1024 * 1024 // 4 MB

/**
 * Compute the MD5 hex digest of a File by streaming it in chunks.
 * Never loads the whole file into memory — safe for large videos.
 */
export function md5File(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const spark = new SparkMD5.ArrayBuffer()
    const reader = new FileReader()
    const total = Math.ceil(file.size / CHUNK_SIZE)
    let current = 0

    reader.onload = (e) => {
      spark.append(e.target!.result as ArrayBuffer)
      current += 1
      if (current < total) {
        loadNext()
      } else {
        resolve(spark.end())
      }
    }
    reader.onerror = () => reject(reader.error)

    function loadNext() {
      const start = current * CHUNK_SIZE
      const end = Math.min(start + CHUNK_SIZE, file.size)
      reader.readAsArrayBuffer(file.slice(start, end))
    }

    loadNext()
  })
}
