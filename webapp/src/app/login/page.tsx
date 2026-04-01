'use client'

import { useState, FormEvent, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'

function LoginForm() {
  const searchParams = useSearchParams()
  const rawFrom = searchParams.get('from') || '/dashboard'
  const from = rawFrom === '/' ? '/dashboard' : rawFrom

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Login failed')
        setLoading(false)
        return
      }

      // Force full page navigation to ensure cookie is sent
      window.location.href = from
    } catch {
      setError('Network error. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      {/* Background CSS animation via global style tag */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes float1 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(-80px,80px)} }
        @keyframes float2 { 0%,100%{transform:translate(0,0)} 50%{transform:translate(60px,-60px)} }
        @keyframes float3 { 0%,100%{transform:translate(-50%,-50%)} 50%{transform:translate(-50%,calc(-50% + 40px))} }
        @keyframes spin { to{transform:rotate(360deg)} }
        .login-input { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); color:white; padding:0.75rem 1rem; font-size:0.9375rem; border-radius:10px; width:100%; box-sizing:border-box; outline:none; font-family:inherit; }
        .login-input::placeholder { color:rgba(255,255,255,0.3); }
        .login-input:focus { border-color:#2563EB; box-shadow:0 0 0 3px rgba(37,99,235,0.2); background:rgba(255,255,255,0.08); }
        .login-btn:hover:not(:disabled) { transform:translateY(-1px); box-shadow:0 6px 24px rgba(37,99,235,0.4) !important; }
        .login-btn:disabled { opacity:0.5; cursor:not-allowed; }
      `}} />

      {/* Animated BG orbs */}
      <div style={styles.bg}>
        <div style={{ ...styles.orb, width:600, height:600, background:'#2563EB', top:-200, right:-100, animation:'float1 20s ease-in-out infinite' }} />
        <div style={{ ...styles.orb, width:400, height:400, background:'#10B981', bottom:-100, left:-100, animation:'float2 25s ease-in-out infinite' }} />
        <div style={{ ...styles.orb, width:300, height:300, background:'#8B5CF6', top:'50%', left:'50%', animation:'float3 18s ease-in-out infinite' }} />
      </div>

      <div style={styles.card}>
        {/* Logo */}
        <div style={{ marginBottom:'2rem' }}>
          <div style={{ display:'flex', alignItems:'center', gap:'0.875rem' }}>
            <div style={styles.logoIcon}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" />
              </svg>
            </div>
            <div>
              <h1 style={{ fontSize:'1.375rem', fontWeight:700, color:'white', letterSpacing:'-0.02em', lineHeight:1.2, margin:0 }}>Nelson Freight</h1>
              <p style={{ fontSize:'0.8rem', color:'rgba(255,255,255,0.5)', margin:'2px 0 0' }}>AI Logistics Platform</p>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display:'flex', flexDirection:'column', gap:'1.25rem' }}>
          <div style={{ display:'flex', flexDirection:'column', gap:'0.375rem' }}>
            <label htmlFor="username" style={styles.label}>Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="login-input"
              placeholder="Enter your username"
              autoComplete="username"
              autoFocus
              required
            />
          </div>

          <div style={{ display:'flex', flexDirection:'column', gap:'0.375rem' }}>
            <label htmlFor="password" style={styles.label}>Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="login-input"
              placeholder="Enter your password"
              autoComplete="current-password"
              required
            />
          </div>

          {error && (
            <div style={styles.error}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading || !username || !password} className="login-btn" style={styles.btn}>
            {loading ? (
              <span style={{ width:20, height:20, border:'2px solid rgba(255,255,255,0.3)', borderTopColor:'white', borderRadius:'50%', animation:'spin 0.6s linear infinite', display:'inline-block' }} />
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Footer */}
        <div style={{ marginTop:'2rem', textAlign:'center' }}>
          <p style={{ fontSize:'0.6875rem', color:'rgba(255,255,255,0.3)', letterSpacing:'0.04em', margin:0 }}>
            Freight Intelligence · Rate Explorer · Shipment Tracker
          </p>
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    overflow: 'hidden',
    background: '#0C1B33',
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
  },
  bg: {
    position: 'absolute',
    inset: 0,
    overflow: 'hidden',
  },
  orb: {
    position: 'absolute' as const,
    borderRadius: '50%',
    filter: 'blur(100px)',
    opacity: 0.3,
  },
  card: {
    position: 'relative' as const,
    width: '100%',
    maxWidth: 420,
    margin: '1rem',
    background: 'rgba(255,255,255,0.05)',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 20,
    padding: '2.5rem',
    boxShadow: '0 25px 50px rgba(0,0,0,0.3)',
  },
  logoIcon: {
    width: 48,
    height: 48,
    background: 'linear-gradient(135deg,#2563EB 0%,#1D4ED8 100%)',
    borderRadius: 12,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'white',
    boxShadow: '0 4px 12px rgba(37,99,235,0.4)',
  },
  label: {
    fontSize: '0.8125rem',
    fontWeight: 500,
    color: 'rgba(255,255,255,0.7)',
  },
  error: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.75rem 1rem',
    background: 'rgba(239,68,68,0.12)',
    border: '1px solid rgba(239,68,68,0.25)',
    borderRadius: 10,
    color: '#FCA5A5',
    fontSize: '0.8125rem',
    fontWeight: 500,
  },
  btn: {
    width: '100%',
    padding: '0.8rem',
    background: 'linear-gradient(135deg,#2563EB 0%,#1D4ED8 100%)',
    color: 'white',
    fontWeight: 600,
    fontSize: '0.9375rem',
    border: 'none',
    borderRadius: 10,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: '0.25rem',
    boxShadow: '0 4px 16px rgba(37,99,235,0.3)',
  },
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'#0C1B33' }}>
        <div style={{ width:32, height:32, border:'3px solid rgba(255,255,255,0.2)', borderTopColor:'#2563EB', borderRadius:'50%', animation:'spin 0.6s linear infinite' }} />
      </div>
    }>
      <LoginForm />
    </Suspense>
  )
}
