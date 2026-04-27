import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

export const lessonApi = createApi({
  reducerPath: 'lessonApi',
  baseQuery: fetchBaseQuery({ baseUrl: '/' }),
  endpoints: (builder) => ({
    generateLesson: builder.mutation({
      query: ({ topic, difficulty = 'beginner', use_llm = true }) => ({
        url: 'lesson/generate',
        method: 'POST',
        body: { topic, difficulty, use_llm },
      }),
    }),
    getLesson: builder.query({
      query: (lessonId) => `lesson/${lessonId}`,
    }),
  }),
})

export const { useGenerateLessonMutation, useLazyGetLessonQuery } = lessonApi
