import { configureStore } from '@reduxjs/toolkit'
import { lessonApi } from '../services/lessonApi'

export const store = configureStore({
  reducer: {
    [lessonApi.reducerPath]: lessonApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(lessonApi.middleware),
})
