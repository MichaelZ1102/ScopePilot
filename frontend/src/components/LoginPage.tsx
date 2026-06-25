import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../lib/api'

const styles = {
  container: {
    display: 'flex',
    minHeight: '100vh',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
  } as React.CSSProperties,
  card: {
    background: '#1e1e38',
    borderRadius: 16,
    padding: '2.5rem',
    width: '100%',
    maxWidth: 420,
    boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
  } as React.CSSProperties,
  title: {
    fontSize: '1.75rem',
    fontWeight: 700,
    color: '#fff',
    textAlign: 'center',
    marginBottom: '0.5rem',
  } as React.CSSProperties,
  subtitle: {
    color: '#888',
    textAlign: 'center',
    marginBottom: '2rem',
    fontSize: '0.9rem',
  } as React.CSSProperties,
  inputGroup: {
    marginBottom: '1.25rem',
  } as React.CSSProperties,
  label: {
    display: 'block',
    color: '#ccc',
    fontSize: '0.85rem',
    marginBottom: '0.4rem',
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '0.75rem 1rem',
    borderRadius: 8,
    border: '1px solid #333',
    background: '#2a2a4a',
    color: '#fff',
    fontSize: '0.95rem',
    outline: 'none',
    boxSizing: 'border-box',
  } as React.CSSProperties,
  button: {
    width: '100%',
    padding: '0.8rem',
    borderRadius: 8,
    border: 'none',
    background: '#4fc3f7',
    color: '#fff',
    fontSize: '1rem',
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: '0.5rem',
  } as React.CSSProperties,
  error: {
    color: '#ff6b6b',
    fontSize: '0.85rem',
    textAlign: 'center',
    marginBottom: '1rem',
    padding: '0.5rem',
    background: 'rgba(255,107,107,0.1)',
    borderRadius: 6,
  } as React.CSSProperties,
  toggle: {
    color: '#4fc3f7',
    cursor: 'pointer',
    textAlign: 'center',
    marginTop: '1rem',
    fontSize: '0.9rem',
  } as React.CSSProperties,
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isRegister) {
        const res = await register(email, name, password)
        localStorage.setItem('token', res.access_token)
        localStorage.setItem('user', JSON.stringify(res.user))
      } else {
        const res = await login(email, password)
        localStorage.setItem('token', res.access_token)
        localStorage.setItem('user', JSON.stringify(res.user))
      }
      navigate('/')
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response: { data: { detail: string } } }).response?.data?.detail ?? '请求失败，请重试')
          : '网络错误，请检查连接'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.title}>🚀 ScopePilot</div>
        <div style={styles.subtitle}>AI Sprint Analysis Platform</div>

        {error && <div style={styles.error}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>邮箱</label>
            <input
              style={styles.input}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              required
            />
          </div>

          {isRegister && (
            <div style={styles.inputGroup}>
              <label style={styles.label}>名称</label>
              <input
                style={styles.input}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your Name"
                required
              />
            </div>
          )}

          <div style={styles.inputGroup}>
            <label style={styles.label}>密码</label>
            <input
              style={styles.input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={4}
            />
          </div>

          <button style={styles.button} type="submit" disabled={loading}>
            {loading ? '处理中...' : isRegister ? '注册' : '登录'}
          </button>
        </form>

        <div
          style={styles.toggle}
          onClick={() => {
            setIsRegister(!isRegister)
            setError('')
          }}
        >
          {isRegister ? '已有账号？点击登录' : '没有账号？点击注册'}
        </div>
      </div>
    </div>
  )
}
