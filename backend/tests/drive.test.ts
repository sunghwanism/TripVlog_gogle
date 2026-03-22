import { SkipFileError, listFiles, downloadFile } from '../src/services/drive'

// ─── SkipFileError ────────────────────────────────────────────────────────────

describe('SkipFileError', () => {
  it('is an instance of Error', () => {
    const err = new SkipFileError('too large')
    expect(err).toBeInstanceOf(Error)
    expect(err).toBeInstanceOf(SkipFileError)
  })

  it('stores reason and sets name', () => {
    const err = new SkipFileError('too large')
    expect(err.reason).toBe('too large')
    expect(err.name).toBe('SkipFileError')
  })

  it('uses reason as message when no message provided', () => {
    const err = new SkipFileError('file exceeds limit')
    expect(err.message).toBe('file exceeds limit')
  })

  it('uses custom message when provided', () => {
    const err = new SkipFileError('reason', 'custom message')
    expect(err.message).toBe('custom message')
    expect(err.reason).toBe('reason')
  })
})

// ─── downloadFile — size routing ──────────────────────────────────────────────

describe('downloadFile', () => {
  const MB = 1024 * 1024
  const mockStream = { pipe: jest.fn() }

  function makeDrive(streamOrError: unknown) {
    return {
      files: {
        get: jest.fn().mockImplementation((_params: unknown, opts: { responseType?: string }) => {
          if (streamOrError instanceof Error) return Promise.reject(streamOrError)
          return Promise.resolve({ data: streamOrError })
        }),
      },
    } as unknown as import('googleapis').drive_v3.Drive
  }

  it('throws SkipFileError for files > 500 MB', async () => {
    const drive = makeDrive(mockStream)
    const SIZE = 501 * MB
    await expect(downloadFile(drive, 'file-id', SIZE)).rejects.toBeInstanceOf(SkipFileError)
  })

  it('throws SkipFileError with descriptive reason for oversized file', async () => {
    const drive = makeDrive(mockStream)
    const SIZE = 600 * MB
    try {
      await downloadFile(drive, 'file-id', SIZE)
      fail('should have thrown')
    } catch (err) {
      expect(err).toBeInstanceOf(SkipFileError)
      expect((err as SkipFileError).reason).toMatch(/500 MB/)
    }
  })

  it('calls drive.files.get with alt=media for files < 50 MB', async () => {
    const drive = makeDrive(mockStream)
    const SIZE = 10 * MB
    await downloadFile(drive, 'target-file', SIZE)
    expect(drive.files.get).toHaveBeenCalledWith(
      { fileId: 'target-file', alt: 'media' },
      expect.objectContaining({ responseType: 'stream' }),
    )
  })

  it('does not throw for exactly 50 MB (chunked threshold)', async () => {
    const drive = makeDrive(mockStream)
    // 50 MB triggers chunked path — just verify it returns without SkipFileError
    // Chunked path runs async; we catch the PassThrough stream before it errors
    const result = await downloadFile(drive, 'file-id', 50 * MB)
    expect(result).toBeDefined()
  })
})

// ─── listFiles — filtering ─────────────────────────────────────────────────────

describe('listFiles', () => {
  function makeDriveWithFiles(files: object[], nextPageToken?: string) {
    return {
      files: {
        list: jest.fn().mockResolvedValue({
          data: { files, nextPageToken: nextPageToken ?? null },
        }),
      },
    } as unknown as import('googleapis').drive_v3.Drive
  }

  it('yields supported MIME types', async () => {
    const drive = makeDriveWithFiles([
      { id: '1', name: 'photo.jpg', mimeType: 'image/jpeg', size: '1024', createdTime: '2026-01-01T00:00:00Z' },
      { id: '2', name: 'clip.mp4', mimeType: 'video/mp4', size: '2048', createdTime: '2026-01-01T01:00:00Z' },
      { id: '3', name: 'doc.pdf', mimeType: 'application/pdf', size: '512', createdTime: '2026-01-01T02:00:00Z' },
    ])

    const results: import('../src/services/drive').DriveFile[][] = []
    for await (const batch of listFiles(drive, 'folder-id')) {
      results.push(batch)
    }

    const allFiles = results.flat()
    expect(allFiles).toHaveLength(2)
    expect(allFiles.map((f) => f.mimeType)).toEqual(['image/jpeg', 'video/mp4'])
  })

  it('excludes files with missing id or name', async () => {
    const drive = makeDriveWithFiles([
      { id: '1', name: 'ok.jpg', mimeType: 'image/jpeg', size: '1024', createdTime: '2026-01-01T00:00:00Z' },
      { name: 'no-id.jpg', mimeType: 'image/jpeg', size: '512', createdTime: '2026-01-01T00:00:00Z' },
      { id: '3', mimeType: 'image/jpeg', size: '512', createdTime: '2026-01-01T00:00:00Z' },
    ])

    const results: import('../src/services/drive').DriveFile[][] = []
    for await (const batch of listFiles(drive, 'folder-id')) {
      results.push(batch)
    }

    expect(results.flat()).toHaveLength(1)
    expect(results.flat()[0].id).toBe('1')
  })

  it('handles empty folder (no files)', async () => {
    const drive = makeDriveWithFiles([])
    const results: import('../src/services/drive').DriveFile[][] = []
    for await (const batch of listFiles(drive, 'empty-folder')) {
      results.push(batch)
    }
    expect(results).toHaveLength(0)
  })

  it('supports all 5 MIME types', async () => {
    const supported = [
      { id: '1', name: 'a.jpg', mimeType: 'image/jpeg', size: '1', createdTime: '2026-01-01T00:00:00Z' },
      { id: '2', name: 'b.png', mimeType: 'image/png', size: '1', createdTime: '2026-01-01T00:00:00Z' },
      { id: '3', name: 'c.heic', mimeType: 'image/heic', size: '1', createdTime: '2026-01-01T00:00:00Z' },
      { id: '4', name: 'd.mp4', mimeType: 'video/mp4', size: '1', createdTime: '2026-01-01T00:00:00Z' },
      { id: '5', name: 'e.mov', mimeType: 'video/quicktime', size: '1', createdTime: '2026-01-01T00:00:00Z' },
    ]
    const drive = makeDriveWithFiles(supported)
    const results: import('../src/services/drive').DriveFile[][] = []
    for await (const batch of listFiles(drive, 'folder')) {
      results.push(batch)
    }
    expect(results.flat()).toHaveLength(5)
  })
})
