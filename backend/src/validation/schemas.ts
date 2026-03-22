import { z } from 'zod'

export const CreateProjectSchema = z.object({
  folder_id: z.string().min(1).max(255),
  concept_prompt: z.string().min(10).max(5000),
})

export const ProjectIdParamSchema = z.object({
  id: z.string().uuid(),
})

export const GoogleCallbackSchema = z.object({
  code: z.string().min(1),
})

export const PaginationQuerySchema = z.object({
  page: z
    .string()
    .optional()
    .transform((v) => (v ? parseInt(v, 10) : 1))
    .pipe(z.number().int().min(1)),
  limit: z
    .string()
    .optional()
    .transform((v) => (v ? parseInt(v, 10) : 20))
    .pipe(z.number().int().min(1).max(100)),
})

export type CreateProjectInput = z.infer<typeof CreateProjectSchema>
export type PaginationQuery = z.infer<typeof PaginationQuerySchema>
