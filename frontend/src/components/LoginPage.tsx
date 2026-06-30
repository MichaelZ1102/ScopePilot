import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { login, register } from '../lib/api'

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    minHeight: '100vh',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
  },
  card: {
    background: '#1e1e38',
    borderRadius: 16,
    padding: '2.5rem',
    width: '100%',
    maxWidth: 420,
    boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
  },
  title: {
    fontSize: '1.75rem',
    fontWeight: 700,
    color: '#fff',
    textAlign: 'center',
    marginBottom: '0.5rem',
  },
  subtitle: {
    color: '#888',
    textAlign: 'center',
    marginBottom: '2rem',
    fontSize: '0.9rem',
  },
  inputGroup: {
    marginBottom: '1.25rem',
  },
  label: {
    display: 'block',
    color: '#ccc',
    fontSize: '0.85rem',
    marginBottom: '0.4rem',
  },
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
  },
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
  },
  error: {
    color: '#ff6b6b',
    fontSize: '0.85rem',
    textAlign: 'center',
    marginBottom: '1rem',
    padding: '0.5rem',
    background: 'rgba(255,107,107,0.1)',
    borderRadius: 6,
  },
  toggle: {
    color: '#4fc3f7',
    cursor: 'pointer',
    textAlign: 'center',
    marginTop: '1rem',
    fontSize: '0.9rem',
  },
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
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
        await register(email, name, password)
      } else {
        await login(email, password)
      }
      // Token is set as HttpOnly cookie by the server — no localStorage needed
      navigate('/')
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? ((err as { response: { data: { detail: string } } }).response?.data?.detail ?? t('login.error_default'))
          : t('login.error_network')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.title}>{t('app.title')}</div>
        <div style={styles.subtitle}>{t('login.subtitle')}</div>

        {error && <div style={styles.error}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>{t('login.email')}</label>
            <input
              style={styles.input}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('login.placeholder_email')}
              required
            />
          </div>

          {isRegister && (
            <div style={styles.inputGroup}>
              <label style={styles.label}>{t('login.name')}</label>
              <input
                style={styles.input}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('login.placeholder_name')}
                required
              />
            </div>
          )}

          <div style={styles.inputGroup}>
            <label style={styles.label}>{t('login.password')}</label>
            <input
              style={styles.input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('login.placeholder_password')}
              required
              minLength={4}
            />
          </div>

          <button style={styles.button} type="submit" disabled={loading}>
            {loading
              ? t('login.loading')
              : isRegister
                ? t('login.submit_register')
                : t('login.submit_login')}
          </button>
        </form>

        <div
          style={styles.toggle}
          onClick={() => {
            setIsRegister(!isRegister)
            setError('')
          }}
        >
          {isRegister ? t('login.toggle_login') : t('login.toggle_register')}
        </div>
      </div>
    </div>
  )
}
