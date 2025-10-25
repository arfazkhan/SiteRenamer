import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Radio } from 'lucide-react';

const LandingPage = () => {
  const [siteId, setSiteId] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (siteId.trim()) {
      navigate(`/upload/${siteId.trim()}`);
    }
  };

  return (
    <div className="landing-container" data-testid="landing-page">
      <div className="landing-content">
        <div className="landing-header">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem' }}>
            <Radio size={48} color="#3182ce" />
          </div>
          <h1 className="landing-title" data-testid="landing-title">
            Antenna Site Image Sorter
          </h1>
          <p className="landing-subtitle" data-testid="landing-subtitle">
            Organize your telecom installation site images efficiently
          </p>
        </div>

        <form onSubmit={handleSubmit} className="site-id-form" data-testid="site-id-form">
          <label className="form-label" htmlFor="siteId">
            Enter Site ID
          </label>
          <input
            id="siteId"
            type="text"
            className="site-id-input"
            placeholder="e.g., SITE-2024-001"
            value={siteId}
            onChange={(e) => setSiteId(e.target.value)}
            data-testid="site-id-input"
            required
          />
          <button 
            type="submit" 
            className="submit-btn"
            disabled={!siteId.trim()}
            data-testid="submit-site-id-btn"
          >
            Continue to Upload
          </button>
        </form>

        <div style={{ 
          marginTop: '2rem', 
          padding: '1rem', 
          background: '#edf2f7', 
          borderRadius: '12px',
          fontSize: '0.9rem',
          color: '#4a5568'
        }}>
          <p style={{ marginBottom: '0.5rem', fontWeight: '600', color: '#2d3748' }}>How it works:</p>
          <ul style={{ paddingLeft: '1.5rem', lineHeight: '1.6' }}>
            <li>Enter your unique Site ID</li>
            <li>Select category (Alpha, Beta, or Gamma)</li>
            <li>Upload 13 component images with drag & drop</li>
            <li>Download organized images as ZIP</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;