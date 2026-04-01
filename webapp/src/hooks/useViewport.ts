'use client'
import { useState, useEffect } from 'react'

export function useViewport() {
  const [width, setWidth] = useState(1024)

  useEffect(() => {
    const update = () => setWidth(window.innerWidth)
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  return {
    width,
    isMobile: width < 640,
    isTablet: width >= 640 && width < 1024,
    isDesktop: width >= 1024,
    isCompact: width < 640,
  }
}
