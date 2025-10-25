import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, Edit, Upload, ArrowLeft, X } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const UploadPage = () => {
  const { siteId } = useParams();
  const navigate = useNavigate();
  const [activeCategory, setActiveCategory] = useState('alpha');
  const [componentNames, setComponentNames] = useState([]);
  const [uploadedImages, setUploadedImages] = useState({});
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editableNames, setEditableNames] = useState([]);
  const [draggedIndex, setDraggedIndex] = useState(null);
  const fileInputRefs = useRef({});

  useEffect(() => {
    fetchComponentNames();
  }, []);

  useEffect(() => {
    if (componentNames.length > 0) {
      fetchCategoryImages(activeCategory);
    }
  }, [activeCategory, componentNames]);

  const fetchComponentNames = async () => {
    try {
      const response = await axios.get(`${API}/component-names`);
      setComponentNames(response.data.names);
      setEditableNames(response.data.names);
    } catch (error) {
      console.error('Error fetching component names:', error);
      toast.error('Failed to load component names');
    }
  };

  const fetchCategoryImages = async (category) => {
    try {
      const response = await axios.get(`${API}/sites/${siteId}/category/${category}`);
      const imagesMap = {};
      response.data.images.forEach(img => {
        imagesMap[img.component_name] = img.filename;
      });
      setUploadedImages(imagesMap);
    } catch (error) {
      console.error('Error fetching category images:', error);
    }
  };

  const handleFileSelect = async (componentName, file) => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post(
        `${API}/sites/${siteId}/upload?category=${activeCategory}&component_name=${encodeURIComponent(componentName)}`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      
      toast.success(`${componentName} uploaded successfully`);
      fetchCategoryImages(activeCategory);
    } catch (error) {
      console.error('Error uploading file:', error);
      toast.error('Failed to upload image');
    }
  };

  const handleDrop = (e, componentName) => {
    e.preventDefault();
    setDraggedIndex(null);
    
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFileSelect(componentName, files[0]);
    }
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    setDraggedIndex(index);
  };

  const handleDragLeave = () => {
    setDraggedIndex(null);
  };

  const handleDownload = async () => {
    try {
      const response = await axios.get(`${API}/sites/${siteId}/download`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${siteId}_images.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Images downloaded successfully');
    } catch (error) {
      console.error('Error downloading images:', error);
      toast.error('Failed to download images. Make sure you have uploaded some images.');
    }
  };

  const handleSaveComponentNames = async () => {
    try {
      await axios.put(`${API}/component-names`, {
        names: editableNames,
      });
      
      setComponentNames(editableNames);
      setIsEditModalOpen(false);
      toast.success('Component names updated successfully');
    } catch (error) {
      console.error('Error updating component names:', error);
      toast.error('Failed to update component names');
    }
  };

  const getImageUrl = (componentName) => {
    const filename = uploadedImages[componentName];
    if (!filename) return null;
    return `${BACKEND_URL}/uploads/${siteId}/${activeCategory}/${filename}`;
  };

  return (
    <div className="upload-container" data-testid="upload-page">
      <div className="upload-header">
        <div className="header-left">
          <button
            onClick={() => navigate('/')}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: '#3182ce',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '0.5rem',
              fontSize: '0.95rem',
              fontWeight: '600',
            }}
            data-testid="back-to-home-btn"
          >
            <ArrowLeft size={18} />
            Back to Home
          </button>
          <h1 data-testid="upload-page-title">Antenna Site Image Sorter</h1>
          <p className="site-id-display" data-testid="site-id-display">
            Site ID: <strong>{siteId}</strong>
          </p>
        </div>
        <div className="header-actions">
          <button
            className="action-btn edit-btn"
            onClick={() => setIsEditModalOpen(true)}
            data-testid="edit-component-names-btn"
          >
            <Edit size={18} />
            Edit Component Names
          </button>
          <button
            className="action-btn download-btn"
            onClick={handleDownload}
            data-testid="download-zip-btn"
          >
            <Download size={18} />
            Download ZIP
          </button>
        </div>
      </div>

      <div className="upload-content">
        <div className="category-tabs">
          {['alpha', 'beta', 'gamma'].map((category) => (
            <button
              key={category}
              className={`category-tab ${activeCategory === category ? 'active' : ''}`}
              onClick={() => setActiveCategory(category)}
              data-testid={`category-tab-${category}`}
            >
              {category.charAt(0).toUpperCase() + category.slice(1)}
            </button>
          ))}
        </div>

        <div className="images-grid">
          {componentNames.map((componentName, index) => {
            const imageUrl = getImageUrl(componentName);
            return (
              <div key={index} className="image-card" data-testid={`image-card-${index}`}>
                <div className="component-label-container">
                  <span className="component-label" data-testid={`component-label-${index}`}>
                    {componentName}
                  </span>
                  <span className="component-number">{index + 1}/13</span>
                </div>
                <div
                  className={`drop-zone ${draggedIndex === index ? 'drag-over' : ''} ${imageUrl ? 'has-image' : ''}`}
                  onDrop={(e) => handleDrop(e, componentName)}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDragLeave={handleDragLeave}
                  onClick={() => {
                    if (!imageUrl) {
                      fileInputRefs.current[index]?.click();
                    }
                  }}
                  data-testid={`drop-zone-${index}`}
                >
                  {imageUrl ? (
                    <>
                      <img
                        src={imageUrl}
                        alt={componentName}
                        className="preview-image"
                        data-testid={`preview-image-${index}`}
                      />
                      <div className="image-actions">
                        <button
                          className="remove-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            fileInputRefs.current[index]?.click();
                          }}
                          data-testid={`replace-image-btn-${index}`}
                        >
                          Replace Image
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="drop-zone-icon">
                        <Upload />
                      </div>
                      <p className="drop-zone-text">Drop image here or click to browse</p>
                      <p className="drop-zone-hint">Supports JPG, PNG, JPEG</p>
                    </>
                  )}
                </div>
                <input
                  type="file"
                  ref={(el) => (fileInputRefs.current[index] = el)}
                  style={{ display: 'none' }}
                  accept="image/*"
                  onChange={(e) => {
                    const file = e.target.files[0];
                    if (file) {
                      handleFileSelect(componentName, file);
                    }
                  }}
                  data-testid={`file-input-${index}`}
                />
              </div>
            );
          })}
        </div>
      </div>

      {isEditModalOpen && (
        <div className="edit-modal-overlay" onClick={() => setIsEditModalOpen(false)} data-testid="edit-modal-overlay">
          <div className="edit-modal" onClick={(e) => e.stopPropagation()} data-testid="edit-modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2>Edit Component Names</h2>
              <button
                onClick={() => setIsEditModalOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#718096',
                }}
                data-testid="close-modal-btn"
              >
                <X size={24} />
              </button>
            </div>
            <div className="component-name-list">
              {editableNames.map((name, index) => (
                <div key={index} className="component-name-item">
                  <span className="component-name-number">{index + 1}.</span>
                  <input
                    type="text"
                    className="component-name-input"
                    value={name}
                    onChange={(e) => {
                      const newNames = [...editableNames];
                      newNames[index] = e.target.value;
                      setEditableNames(newNames);
                    }}
                    data-testid={`edit-component-name-input-${index}`}
                  />
                </div>
              ))}
            </div>
            <div className="modal-actions">
              <button
                className="action-btn cancel-btn"
                onClick={() => {
                  setEditableNames(componentNames);
                  setIsEditModalOpen(false);
                }}
                data-testid="cancel-edit-btn"
              >
                Cancel
              </button>
              <button
                className="action-btn save-btn"
                onClick={handleSaveComponentNames}
                data-testid="save-component-names-btn"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadPage;