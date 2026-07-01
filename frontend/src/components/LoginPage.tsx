import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { LoaderCircle, ScanSearch } from 'lucide-react'

import { login, register } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { getApiErrorMessage } from '../lib/client'

export default function LoginPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { checkAuth } = useAuth()
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isRegister) {
        await register(email, name, password)
      } else {
        await login(email, password)
      }
      await checkAuth()
      navigate('/')
    } catch (requestError: unknown) {
      setError(getApiErrorMessage(requestError, t('login.error_network')))
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-intro">
        <div className="auth-brand">
          <span><ScanSearch size={21} /></span>
          ScopePilot
        </div>
        <div className="auth-copy">
          <h1>从 Sprint 到实现影响，一处完成分析。</h1>
          <p>连接 Jira、代码仓库、OpenAPI 与 Figma，按 Ticket 提炼需求并生成可执行的分析报告。</p>
        </div>
        <small>ScopePilot Workspace</small>
      </section>

      <section className="auth-main">
        <form className="auth-form" onSubmit={handleSubmit}>
          <span className="workspace-kicker">{isRegister ? 'Create Workspace Account' : 'Welcome Back'}</span>
          <h2>{isRegister ? '创建账号' : '登录 ScopePilot'}</h2>
          <p>{t('login.subtitle')}</p>

          {error && <div className="inline-error">{error}</div>}

          <label className="form-field">
            <span>{t('login.email')}</span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t('login.placeholder_email')} required autoComplete="email" />
          </label>

          {isRegister && (
            <label className="form-field">
              <span>{t('login.name')}</span>
              <input type="text" value={name} onChange={(event) => setName(event.target.value)} placeholder={t('login.placeholder_name')} required autoComplete="name" />
            </label>
          )}

          <label className="form-field">
            <span>{t('login.password')}</span>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t('login.placeholder_password')} required minLength={4} autoComplete={isRegister ? 'new-password' : 'current-password'} />
          </label>

          <button className="button button-primary" type="submit" disabled={loading}>
            {loading && <LoaderCircle className="spin" size={16} />}
            {loading ? t('login.loading') : isRegister ? t('login.submit_register') : t('login.submit_login')}
          </button>

          <button
            className="auth-toggle"
            type="button"
            onClick={() => {
              setIsRegister((current) => !current)
              setError('')
            }}
          >
            {isRegister ? t('login.toggle_login') : t('login.toggle_register')}
          </button>
        </form>
      </section>
    </main>
  )
}
