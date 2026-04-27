import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useGenerateLessonMutation } from './services/lessonApi'

function App() {
  const [topic, setTopic] = useState('Photosynthesis')
  const [lesson, setLesson] = useState(null)
  const [lessonId, setLessonId] = useState('')
  const [svgMarkup, setSvgMarkup] = useState('')
  const [status, setStatus] = useState('Ready')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isPaused, setIsPaused] = useState(false)

  const audioRef = useRef(null)
  const svgHostRef = useRef(null)
  const isPausedRef = useRef(false)

  const [generateLesson, { isLoading }] = useGenerateLessonMutation()

  const topicTree = useMemo(() => {
    if (!lesson) return []
    const childMap = {}
    for (const sub of lesson.subtopics ?? []) {
      if (!sub.parent_id) continue
      if (!childMap[sub.parent_id]) childMap[sub.parent_id] = []
      childMap[sub.parent_id].push(sub)
    }
    return (lesson.svg_nodes ?? []).map((node) => ({
      ...node,
      children: childMap[node.id] ?? [],
    }))
  }, [lesson])

  const clearHighlights = () => {
    const host = svgHostRef.current
    if (!host) return
    host.querySelectorAll('.highlighted').forEach((el) => el.classList.remove('highlighted'))
  }

  const highlightById = (id) => {
    const host = svgHostRef.current
    if (!host) return
    clearHighlights()
    const target = host.querySelector(`#${CSS.escape(id)}`)
    if (target) target.classList.add('highlighted')
  }

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      audioRef.current = null
    }
  }, [])

  async function playFromIndex(index) {
    if (!lesson || !lessonId) return
    if (index < 0 || index >= (lesson.sync_map?.length ?? 0)) {
      setStatus('Playback finished')
      setIsPlaying(false)
      setIsPaused(false)
      clearHighlights()
      return
    }

    stopAudio()
    setCurrentIndex(index)
    setIsPlaying(true)
    setIsPaused(false)

    const segment = lesson.sync_map[index]
    highlightById(segment.id)
    setStatus(`Playing ${index + 1}/${lesson.sync_map.length}`)

    const audio = new Audio(`/audio/${lessonId}/${segment.audio_chunk}`)
    audioRef.current = audio
    audio.onended = () => {
      if (!isPausedRef.current) {
        playFromIndex(index + 1)
      }
    }

    try {
      await audio.play()
    } catch {
      setStatus('Audio playback failed')
      setIsPlaying(false)
    }
  }

  const handleGenerate = async () => {
    const clean = topic.trim()
    if (!clean) return
    setStatus('Generating lesson...')
    stopAudio()
    setIsPlaying(false)
    setIsPaused(false)
    setCurrentIndex(0)

    try {
      const res = await generateLesson({ topic: clean, difficulty: 'beginner', use_llm: true }).unwrap()
      setLesson(res.lesson)
      setLessonId(res.lesson_id)

      const svgResponse = await fetch(res.svg_url)
      const svgText = await svgResponse.text()
      setSvgMarkup(svgText)

      setStatus(`Lesson ready: ${res.lesson.title}`)
    } catch (err) {
      setStatus(`Generation failed: ${err?.data?.detail || err?.message || 'unknown error'}`)
    }
  }

  useEffect(() => {
    isPausedRef.current = isPaused
  }, [isPaused])

  useEffect(() => {
    if (!lesson || !svgHostRef.current) return
    for (const [idx, id] of (lesson.narration_order ?? []).entries()) {
      const target = svgHostRef.current.querySelector(`#${CSS.escape(id)}`)
      if (!target) continue
      target.style.cursor = 'pointer'
      target.onclick = () => playFromIndex(idx)
    }
  }, [lesson, svgMarkup])

  useEffect(() => () => stopAudio(), [stopAudio])

  return (
    <div className="mx-auto flex min-h-screen max-w-[1500px] flex-col gap-4 p-4">
      <header className="rounded-xl bg-white p-4 shadow-sm">
        <h1 className="mb-3 text-2xl font-bold">AI Tutor Interactive Lesson</h1>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="min-w-[320px] rounded-lg border border-slate-300 px-3 py-2"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Enter topic"
          />
          <button
            onClick={handleGenerate}
            disabled={isLoading}
            className="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
          >
            {isLoading ? 'Generating...' : 'Generate lesson'}
          </button>
          <button
            onClick={() => playFromIndex(0)}
            className="rounded-lg bg-slate-700 px-4 py-2 text-white"
            disabled={!lesson}
          >
            Play
          </button>
          <button
            onClick={() => {
              setIsPaused(true)
              if (audioRef.current) audioRef.current.pause()
              setStatus('Paused')
            }}
            className="rounded-lg bg-slate-700 px-4 py-2 text-white"
            disabled={!isPlaying}
          >
            Pause
          </button>
          <button
            onClick={async () => {
              if (!audioRef.current) return
              setIsPaused(false)
              await audioRef.current.play()
              setStatus('Resumed')
            }}
            className="rounded-lg bg-slate-700 px-4 py-2 text-white"
            disabled={!isPlaying}
          >
            Resume
          </button>
          <span className="ml-2 text-sm text-slate-600">{status}</span>
        </div>

        {lesson?.sync_map?.length ? (
          <div className="mt-3 flex items-center gap-3">
            <span className="text-sm text-slate-600">Seek:</span>
            <input
              type="range"
              min={0}
              max={lesson.sync_map.length - 1}
              value={currentIndex}
              onChange={(e) => {
                const idx = Number(e.target.value)
                setCurrentIndex(idx)
                highlightById(lesson.sync_map[idx]?.id)
              }}
              onMouseUp={(e) => playFromIndex(Number(e.target.value))}
              className="w-[420px]"
            />
            <span className="text-sm text-slate-600">
              {currentIndex + 1}/{lesson.sync_map.length}
            </span>
          </div>
        ) : null}
      </header>

      <main className="grid grid-cols-1 gap-4 lg:grid-cols-[380px_1fr]">
        <aside className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold">Topic map</h2>
          {!lesson ? (
            <p className="mt-3 text-sm text-slate-500">Generate a lesson to view structured sub explanations.</p>
          ) : (
            <div className="mt-3 space-y-3">
              {topicTree.map((node) => (
                <div key={node.id} className="rounded-md border border-slate-200 p-3">
                  <button
                    className="cursor-pointer text-left font-semibold text-slate-800 hover:text-blue-700"
                    onClick={() => {
                      const idx = lesson.narration_order.indexOf(node.id)
                      if (idx >= 0) playFromIndex(idx)
                    }}
                  >
                    {node.label}
                  </button>

                  <ul className="mt-2 ml-3 list-disc space-y-2 text-sm text-slate-600" aria-label={`${node.label} sub explanations`}>
                    {node.children.map((sub) => (
                      <li key={sub.id}>
                        <button
                          className="cursor-pointer text-left hover:text-blue-700"
                          onClick={() => {
                            const idx = lesson.narration_order.indexOf(sub.id)
                            if (idx >= 0) playFromIndex(idx)
                          }}
                        >
                          {sub.explanation}
                        </button>
                        {sub.bullet_points?.length ? (
                          <ul className="mt-1 ml-4 list-[circle] space-y-1 text-slate-500">
                            {sub.bullet_points.map((b, i) => (
                              <li key={`${sub.id}-${i}`}>{b}</li>
                            ))}
                          </ul>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </aside>

        <section className="rounded-xl bg-white p-3 shadow-sm">
          <div
            ref={svgHostRef}
            className="overflow-auto rounded-lg border border-slate-200 bg-white"
            dangerouslySetInnerHTML={{ __html: svgMarkup }}
          />
        </section>
      </main>
    </div>
  )
}

export default App
