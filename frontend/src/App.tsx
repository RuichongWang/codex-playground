import { useState } from 'react'
import axios from 'axios'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Architecture {
  components: Array<{id: string; label: string; type: string}>
  connections: Array<{from: string; to: string; label?: string}>
  metadata: Record<string, any>
}

interface GeneratedFile {
  [path: string]: string
}

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [architecture, setArchitecture] = useState<Architecture | null>(null)
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'upload' | 'architecture' | 'preview'>('upload')

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setError(null)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file first')
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Upload and parse diagram
      const formData = new FormData()
      formData.append('file', selectedFile)

      const parseResponse = await axios.post(`${API_BASE_URL}/api/parse-diagram`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })

      const arch = parseResponse.data.architecture
      setArchitecture(arch)
      setActiveTab('architecture')

    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to parse diagram')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!architecture) return

    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(`${API_BASE_URL}/api/generate-preview`, architecture)
      setGeneratedFiles(response.data.files)
      setActiveTab('preview')
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to generate code')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = async () => {
    if (!architecture) return

    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(`${API_BASE_URL}/api/generate-app`, architecture, {
        responseType: 'blob'
      })

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'generated-app.zip')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)

    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to download app')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Enhanced Coding Agent</h1>
        <p>Generate complete applications from architecture diagrams</p>
      </header>

      <div className="tabs">
        <button
          className={activeTab === 'upload' ? 'active' : ''}
          onClick={() => setActiveTab('upload')}
        >
          1. Upload Diagram
        </button>
        <button
          className={activeTab === 'architecture' ? 'active' : ''}
          onClick={() => setActiveTab('architecture')}
          disabled={!architecture}
        >
          2. View Architecture
        </button>
        <button
          className={activeTab === 'preview' ? 'active' : ''}
          onClick={() => setActiveTab('preview')}
          disabled={!generatedFiles}
        >
          3. Preview Code
        </button>
      </div>

      {error && (
        <div className="error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="content">
        {activeTab === 'upload' && (
          <div className="upload-section">
            <div className="file-input">
              <input
                type="file"
                accept=".vsdx,.vdx,.png,.jpg,.jpeg"
                onChange={handleFileSelect}
                id="file-upload"
              />
              <label htmlFor="file-upload" className="file-label">
                {selectedFile ? selectedFile.name : 'Choose diagram file (VSDX or PNG)'}
              </label>
            </div>

            <button
              onClick={handleUpload}
              disabled={!selectedFile || loading}
              className="primary-button"
            >
              {loading ? 'Parsing...' : 'Parse Diagram'}
            </button>

            <div className="help-text">
              <h3>Supported Formats:</h3>
              <ul>
                <li><strong>VSDX/VDX:</strong> Lucidchart exports (recommended)</li>
                <li><strong>PNG/JPG:</strong> Screenshot fallback using AI vision</li>
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'architecture' && architecture && (
          <div className="architecture-section">
            <h2>Parsed Architecture</h2>

            <div className="arch-grid">
              <div className="arch-panel">
                <h3>Components ({architecture.components.length})</h3>
                <ul className="component-list">
                  {architecture.components.map((comp) => (
                    <li key={comp.id}>
                      <span className="comp-type">{comp.type}</span>
                      <span className="comp-label">{comp.label}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="arch-panel">
                <h3>Connections ({architecture.connections.length})</h3>
                <ul className="connection-list">
                  {architecture.connections.map((conn, idx) => (
                    <li key={idx}>
                      <span className="conn-from">{conn.from}</span>
                      <span className="conn-arrow">→</span>
                      <span className="conn-to">{conn.to}</span>
                      {conn.label && <span className="conn-label">({conn.label})</span>}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="actions">
              <button onClick={handleGenerate} disabled={loading} className="primary-button">
                {loading ? 'Generating...' : 'Generate Application'}
              </button>
            </div>
          </div>
        )}

        {activeTab === 'preview' && generatedFiles && (
          <div className="preview-section">
            <h2>Generated Code</h2>

            <div className="file-tree">
              {Object.entries(generatedFiles).map(([path, content]) => (
                <details key={path} className="file-item">
                  <summary>{path}</summary>
                  <pre className="code-block">
                    <code>{content}</code>
                  </pre>
                </details>
              ))}
            </div>

            <div className="actions">
              <button onClick={handleDownload} disabled={loading} className="primary-button">
                {loading ? 'Preparing...' : 'Download Application (.zip)'}
              </button>
            </div>
          </div>
        )}
      </div>

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
        </div>
      )}
    </div>
  )
}

export default App
