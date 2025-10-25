import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, Edit, Upload, ArrowLeft, X, Plus, Trash2, Edit2, FileText } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const UploadPage = () => {
  const { siteId } = useParams();
  const navigate = useNavigate();
  const [activeCategory, setActiveCategory] = useState('alpha');
  const [componentNames, setComponentNames] = useState([]);
  const [categoryNames, setCategoryNames] = useState({ alpha: 'Alpha', beta: 'Beta', gamma: 'Gamma' });
  const [uploadedImages, setUploadedImages] = useState({});
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isCategoryEditModalOpen, setIsCategoryEditModalOpen] = useState(false);
  const [isNamingFormatModalOpen, setIsNamingFormatModalOpen] = useState(false);
  const [editableNames, setEditableNames] = useState([]);
  const [editableCategoryNames, setEditableCategoryNames] = useState({});
  const [namingFormat, setNamingFormat] = useState('{site_id}_{category}_{component_name}');
  const [editableNamingFormat, setEditableNamingFormat] = useState('');
  const [draggedIndex, setDraggedIndex] = useState(null);
  const fileInputRefs = useRef({});

  useEffect(() => {
    fetchComponentNames();
    fetchCategoryNames();
    fetchNamingFormat();
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

  const fetchCategoryNames = async () => {
    try {
      const response = await axios.get(`${API}/category-names`);
      setCategoryNames(response.data.categories);
      setEditableCategoryNames(response.data.categories);
    } catch (error) {
      console.error('Error fetching category names:', error);
    }
  };

  const fetchNamingFormat = async () => {
    try {
      const response = await axios.get(`${API}/naming-format`);
      setNamingFormat(response.data.format);
      setEditableNamingFormat(response.data.format);
    } catch (error) {
      console.error('Error fetching naming format:', error);
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

  const handleSaveCategoryNames = async () => {
    try {
      await axios.put(`${API}/category-names`, {
        categories: editableCategoryNames,
      });
      
      setCategoryNames(editableCategoryNames);
      setIsCategoryEditModalOpen(false);
      toast.success('Category names updated successfully');
    } catch (error) {
      console.error('Error updating category names:', error);
      toast.error('Failed to update category names');
    }
  };

  const handleSaveNamingFormat = async () => {
    try {
      await axios.put(`${API}/naming-format`, {
        format: editableNamingFormat,
      });
      
      setNamingFormat(editableNamingFormat);
      setIsNamingFormatModalOpen(false);
      toast.success('Naming format updated successfully');
    } catch (error) {
      console.error('Error updating naming format:', error);
      toast.error(error.response?.data?.detail || 'Failed to update naming format');
    }
  };

  const handleAddComponent = () => {
    const newName = `New Component ${editableNames.length + 1}`;
    setEditableNames([...editableNames, newName]);
  };

  const handleRemoveComponent = (index) => {
    if (editableNames.length <= 1) {
      toast.error('Must have at least one component');
      return;
    }
    const newNames = editableNames.filter((_, i) => i !== index);
    setEditableNames(newNames);
  };

  const insertPlaceholder = (placeholder) => {
    setEditableNamingFormat(editableNamingFormat + placeholder);
  };

  const getPreviewFilename = () => {
    let preview = editableNamingFormat;
    preview = preview.replace(/{site_id}/g, siteId);
    preview = preview.replace(/{category}/g, activeCategory);
    preview = preview.replace(/{component_name}/g, 'Antenna_Front_View');
    preview = preview.replace(/[^a-zA-Z0-9_-]/g, '_');
    return preview + '.jpg';
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
            onClick={() => setIsNamingFormatModalOpen(true)}
            data-testid="edit-naming-format-btn"
          >
            <FileText size={18} />
            File Naming
          </button>
          <button
            className="action-btn edit-btn"
            onClick={() => setIsCategoryEditModalOpen(true)}
            data-testid="edit-category-names-btn"
          >
            <Edit2 size={18} />
            Edit Categories
          </button>
          <button
            className="action-btn edit-btn"
            onClick={() => setIsEditModalOpen(true)}
            data-testid="edit-component-names-btn"
          >
            <Edit size={18} />
            Edit Components
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
              {categoryNames[category] || category.charAt(0).toUpperCase() + category.slice(1)}
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
                  <span className="component-number">{index + 1}/{componentNames.length}</span>
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

      {/* Edit Component Names Modal */}
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
                  <button
                    onClick={() => handleRemoveComponent(index)}
                    style={{
                      background: '#fed7d7',
                      color: '#c53030',
                      border: 'none',
                      borderRadius: '6px',
                      padding: '0.5rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      transition: 'background 0.2s',
                    }}
                    data-testid={`remove-component-btn-${index}`}
                    onMouseEnter={(e) => e.target.style.background = '#fc8181'}
                    onMouseLeave={(e) => e.target.style.background = '#fed7d7'}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={handleAddComponent}
              style={{
                width: '100%',
                marginTop: '1rem',
                padding: '0.75rem',
                background: '#edf2f7',
                color: '#2d3748',
                border: '2px dashed #cbd5e0',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '600',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                transition: 'all 0.2s',
              }}
              data-testid="add-component-btn"
              onMouseEnter={(e) => {
                e.target.style.background = '#e2e8f0';
                e.target.style.borderColor = '#3182ce';
              }}
              onMouseLeave={(e) => {
                e.target.style.background = '#edf2f7';
                e.target.style.borderColor = '#cbd5e0';
              }}
            >
              <Plus size={18} />
              Add Component
            </button>
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

      {/* Edit Category Names Modal */}
      {isCategoryEditModalOpen && (
        <div className="edit-modal-overlay" onClick={() => setIsCategoryEditModalOpen(false)} data-testid="category-edit-modal-overlay">
          <div className="edit-modal" onClick={(e) => e.stopPropagation()} data-testid="category-edit-modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2>Edit Category Names</h2>
              <button
                onClick={() => setIsCategoryEditModalOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#718096',
                }}
                data-testid="close-category-modal-btn"
              >
                <X size={24} />
              </button>
            </div>
            <div className="component-name-list">
              {['alpha', 'beta', 'gamma'].map((key, index) => (
                <div key={key} className="component-name-item">
                  <span className="component-name-number">{index + 1}.</span>
                  <input
                    type="text"
                    className="component-name-input"
                    value={editableCategoryNames[key] || ''}
                    onChange={(e) => {
                      setEditableCategoryNames({
                        ...editableCategoryNames,
                        [key]: e.target.value
                      });
                    }}
                    placeholder={`Category ${index + 1}`}
                    data-testid={`edit-category-name-input-${key}`}
                  />
                </div>
              ))}
            </div>
            <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
              <button
                className="action-btn cancel-btn"
                onClick={() => {
                  setEditableCategoryNames(categoryNames);
                  setIsCategoryEditModalOpen(false);
                }}
                data-testid="cancel-category-edit-btn"
              >
                Cancel
              </button>
              <button
                className="action-btn save-btn"
                onClick={handleSaveCategoryNames}
                data-testid="save-category-names-btn"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Naming Format Modal */}
      {isNamingFormatModalOpen && (
        <div className="edit-modal-overlay" onClick={() => setIsNamingFormatModalOpen(false)} data-testid="naming-format-modal-overlay">
          <div className="edit-modal" onClick={(e) => e.stopPropagation()} data-testid="naming-format-modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2>Edit File Naming Format</h2>
              <button
                onClick={() => setIsNamingFormatModalOpen(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#718096',
                }}
                data-testid="close-naming-modal-btn"
              >
                <X size={24} />
              </button>
            </div>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.5rem' }}>
                Naming Format
              </label>
              <input
                type="text"
                className="component-name-input"
                value={editableNamingFormat}
                onChange={(e) => setEditableNamingFormat(e.target.value)}
                placeholder="e.g., {site_id}_{category}_{component_name}"
                data-testid="naming-format-input"
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <p style={{ fontSize: '0.85rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.5rem' }}>Available Placeholders:</p>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {['{site_id}', '{category}', '{component_name}'].map((placeholder) => (
                  <button
                    key={placeholder}
                    onClick={() => insertPlaceholder(placeholder)}
                    style={{
                      padding: '0.5rem 0.75rem',
                      background: '#edf2f7',
                      border: '1px solid #cbd5e0',
                      borderRadius: '6px',
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                      fontFamily: 'monospace',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.background = '#e2e8f0';
                      e.target.style.borderColor = '#3182ce';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.background = '#edf2f7';
                      e.target.style.borderColor = '#cbd5e0';
                    }}
                  >
                    {placeholder}
                  </button>
                ))}
              </div>
            </div>

            <div style={{
              padding: '1rem',
              background: '#f7fafc',
              borderRadius: '8px',
              marginBottom: '1rem',
              border: '1px solid #e2e8f0'
            }}>
              <p style={{ fontSize: '0.85rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.5rem' }}>Preview:</p>
              <p style={{ fontSize: '0.9rem', fontFamily: 'monospace', color: '#3182ce', wordBreak: 'break-all' }}>
                {getPreviewFilename()}
              </p>
            </div>

            <div style={{
              padding: '0.75rem',
              background: '#fff5e6',
              borderRadius: '8px',
              fontSize: '0.8rem',
              color: '#744210',
              marginBottom: '1rem',
              lineHeight: '1.4'
            }}>
              <strong>Note:</strong> Use placeholders to customize how files are named. Spaces will be replaced with underscores.
            </div>

            <div className="modal-actions">
              <button
                className="action-btn cancel-btn"
                onClick={() => {
                  setEditableNamingFormat(namingFormat);
                  setIsNamingFormatModalOpen(false);
                }}
                data-testid="cancel-naming-edit-btn"
              >
                Cancel
              </button>
              <button
                className="action-btn save-btn"
                onClick={handleSaveNamingFormat}
                data-testid="save-naming-format-btn"
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