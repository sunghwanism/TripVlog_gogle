import {
  CreateProjectSchema,
  ProjectIdParamSchema,
  GoogleCallbackSchema,
  PaginationQuerySchema,
} from '../src/validation/schemas'

describe('CreateProjectSchema', () => {
  it('accepts valid input', () => {
    const result = CreateProjectSchema.safeParse({
      folder_id: 'abc123folder',
      concept_prompt: 'A cinematic summer road trip',
    })
    expect(result.success).toBe(true)
  })

  it('rejects empty folder_id', () => {
    const result = CreateProjectSchema.safeParse({
      folder_id: '',
      concept_prompt: 'A cinematic summer road trip',
    })
    expect(result.success).toBe(false)
  })

  it('rejects concept_prompt shorter than 10 chars', () => {
    const result = CreateProjectSchema.safeParse({
      folder_id: 'abc123',
      concept_prompt: 'short',
    })
    expect(result.success).toBe(false)
  })

  it('rejects concept_prompt longer than 5000 chars', () => {
    const result = CreateProjectSchema.safeParse({
      folder_id: 'abc123',
      concept_prompt: 'a'.repeat(5001),
    })
    expect(result.success).toBe(false)
  })

  it('accepts concept_prompt exactly 10 chars', () => {
    const result = CreateProjectSchema.safeParse({
      folder_id: 'abc123',
      concept_prompt: '1234567890',
    })
    expect(result.success).toBe(true)
  })

  it('rejects folder_id longer than 255 chars', () => {
    const result = CreateProjectSchema.safeParse({
      folder_id: 'a'.repeat(256),
      concept_prompt: 'Valid concept prompt here',
    })
    expect(result.success).toBe(false)
  })

  it('rejects missing fields', () => {
    expect(CreateProjectSchema.safeParse({}).success).toBe(false)
    expect(CreateProjectSchema.safeParse({ folder_id: 'abc' }).success).toBe(false)
  })
})

describe('ProjectIdParamSchema', () => {
  it('accepts valid UUID', () => {
    const result = ProjectIdParamSchema.safeParse({
      id: '550e8400-e29b-41d4-a716-446655440000',
    })
    expect(result.success).toBe(true)
  })

  it('rejects non-UUID strings', () => {
    expect(ProjectIdParamSchema.safeParse({ id: 'not-a-uuid' }).success).toBe(false)
    expect(ProjectIdParamSchema.safeParse({ id: '12345' }).success).toBe(false)
    expect(ProjectIdParamSchema.safeParse({ id: '' }).success).toBe(false)
  })

  it('rejects missing id', () => {
    expect(ProjectIdParamSchema.safeParse({}).success).toBe(false)
  })
})

describe('GoogleCallbackSchema', () => {
  it('accepts a non-empty code', () => {
    const result = GoogleCallbackSchema.safeParse({ code: '4/0AY0e-g7abc' })
    expect(result.success).toBe(true)
  })

  it('rejects empty code', () => {
    expect(GoogleCallbackSchema.safeParse({ code: '' }).success).toBe(false)
  })

  it('rejects missing code', () => {
    expect(GoogleCallbackSchema.safeParse({}).success).toBe(false)
  })
})

describe('PaginationQuerySchema', () => {
  it('defaults page to 1 and limit to 20 when omitted', () => {
    const result = PaginationQuerySchema.safeParse({})
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.page).toBe(1)
      expect(result.data.limit).toBe(20)
    }
  })

  it('parses string numbers correctly', () => {
    const result = PaginationQuerySchema.safeParse({ page: '3', limit: '50' })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.page).toBe(3)
      expect(result.data.limit).toBe(50)
    }
  })

  it('rejects limit above 100', () => {
    expect(PaginationQuerySchema.safeParse({ limit: '101' }).success).toBe(false)
  })

  it('rejects page below 1', () => {
    expect(PaginationQuerySchema.safeParse({ page: '0' }).success).toBe(false)
  })

  it('rejects non-numeric strings', () => {
    expect(PaginationQuerySchema.safeParse({ page: 'abc' }).success).toBe(false)
  })
})
