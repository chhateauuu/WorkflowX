import React, { useState, useEffect } from "react";
import { 
  FaUserCircle, 
  FaBell, 
  FaCog, 
  FaSearch, 
  FaChevronDown,
  FaSignOutAlt,
  FaUser,
  FaMoon,
  FaSun,
  FaBars,
  FaTimes,
  FaChartLine,
  FaHome
} from "react-icons/fa";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate, Link, useLocation } from "react-router-dom";

const Navbar = ({ darkMode, toggleDarkMode }) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  
  // For debugging
  useEffect(() => {
    if (currentUser) {
      console.log("Navbar: Current user data:", currentUser);
    } else {
      console.log("Navbar: No current user");
    }
  }, [currentUser]);
  
  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setDropdownOpen(false);
      setNotificationsOpen(false);
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  // Close mobile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (mobileMenuOpen && !e.target.closest('.mobile-menu') && !e.target.closest('.mobile-menu-toggle')) {
        setMobileMenuOpen(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [mobileMenuOpen]);

  const handleLogout = () => {
    logout();
    navigate('/login');
    setDropdownOpen(false);
  };

  // Helper function to get display name
  const getUserDisplayName = () => {
    if (!currentUser) return 'User';
    
    if (currentUser.name) return currentUser.name;
    if (currentUser.email) return currentUser.email;
    
    return 'User';
  };

  return (
    <motion.nav 
      className="navbar"
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ type: "spring", stiffness: 120 }}
    >
      <div className="navbar-left">
        <motion.div 
          className="brand-container"
          whileHover={{ scale: 1.05 }}
          transition={{ type: "spring", stiffness: 400 }}
          onClick={() => navigate('/')}
        >
          <span className="brand">WorkflowX</span>
        </motion.div>
        
        {/* Desktop Navigation Links */}
        <div className="nav-links desktop-only">
          <motion.span 
            as={Link}
            to="/"
            className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
            whileHover={{ scale: 1.1 }}
            onClick={() => navigate('/')}
          >
            <FaHome className="nav-icon-small" />
            Your Assistant
          </motion.span>
          <motion.span 
            as={Link}
            to="/analytics"
            className={`nav-link ${location.pathname === '/analytics' ? 'active' : ''}`}
            whileHover={{ scale: 1.1 }}
            onClick={() => navigate('/analytics')}
          >
            <FaChartLine className="nav-icon-small" />
            Analytics
          </motion.span>
        </div>
        
        {/* Mobile Menu Toggle */}
        <div 
          className="mobile-menu-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? <FaTimes className="menu-icon" /> : <FaBars className="menu-icon" />}
        </div>
      </div>
      
      <div className="navbar-center">
        <div className={`search-container ${searchFocused ? 'focused' : ''}`}>
          <FaSearch className="search-icon" />
          <input 
            type="text" 
            placeholder="Search..." 
            className="search-input"
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
          />
        </div>
      </div>
      
      <div className="navbar-right">
        <motion.div 
          className="nav-icon-container"
          whileHover={{ scale: 1.1 }}
          onClick={(e) => {
            e.stopPropagation();
            setNotificationsOpen(!notificationsOpen);
            setDropdownOpen(false);
          }}
        >
          <FaBell className="nav-icon" />
          <span className="notification-badge">3</span>
          
          <AnimatePresence>
            {notificationsOpen && (
              <motion.div 
                className="dropdown-menu notifications-menu"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.2 }}
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="dropdown-header">Notifications</h3>
                <div className="notification-item unread">
                  <p>New message received</p>
                  <span className="notification-time">2m ago</span>
                </div>
                <div className="notification-item unread">
                  <p>Your project was approved</p>
                  <span className="notification-time">1h ago</span>
                </div>
                <div className="notification-item">
                  <p>Weekly summary available</p>
                  <span className="notification-time">1d ago</span>
                </div>
                <div className="dropdown-footer">
                  <span>View all notifications</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
        
        <motion.div 
          className="nav-icon-container"
          whileHover={{ scale: 1.1 }}
        >
          <FaCog className="nav-icon" />
        </motion.div>
        
        {currentUser ? (
          <motion.div 
            className="profile-container"
            onClick={(e) => {
              e.stopPropagation();
              setDropdownOpen(!dropdownOpen);
              setNotificationsOpen(false);
            }}
            whileHover={{ scale: 1.05 }}
          >
            <FaUserCircle className="profile-icon" />
            <span className="profile-name">{getUserDisplayName()}</span>
            <FaChevronDown className={`dropdown-arrow ${dropdownOpen ? 'open' : ''}`} />
            
            <AnimatePresence>
              {dropdownOpen && (
                <motion.div 
                  className="dropdown-menu profile-menu"
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.2 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="dropdown-item">
                    <FaUser className="dropdown-icon" />
                    <span>My Profile</span>
                  </div>
                  <div className="dropdown-item" onClick={toggleDarkMode}>
                    {darkMode ? (
                      <>
                        <FaSun className="dropdown-icon" />
                        <span>Light Mode</span>
                      </>
                    ) : (
                      <>
                        <FaMoon className="dropdown-icon" />
                        <span>Dark Mode</span>
                      </>
                    )}
                  </div>
                  <div className="dropdown-divider"></div>
                  <div 
                    className="dropdown-item logout"
                    onClick={handleLogout}
                  >
                    <FaSignOutAlt className="dropdown-icon" />
                    <span>Sign Out</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ) : (
          <motion.div 
            className="login-button"
            whileHover={{ scale: 1.05 }}
            onClick={() => navigate('/login')}
          >
            Sign In
          </motion.div>
        )}
      </div>
      
      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div 
            className="mobile-menu"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.2 }}
          >
            <div className="mobile-menu-items">
              <div 
                className={`mobile-menu-item ${location.pathname === '/' ? 'active' : ''}`}
                onClick={() => {
                  navigate('/');
                  setMobileMenuOpen(false);
                }}
              >
                <FaHome className="mobile-menu-item-icon" />
                <span>Your Assistant</span>
              </div>
              <div 
                className={`mobile-menu-item ${location.pathname === '/analytics' ? 'active' : ''}`}
                onClick={() => {
                  navigate('/analytics');
                  setMobileMenuOpen(false);
                }}
              >
                <FaChartLine className="mobile-menu-item-icon" />
                <span>Analytics</span>
              </div>
              <div className="mobile-menu-divider"></div>
              {currentUser && (
                <div className="mobile-menu-user-info">
                  <FaUserCircle className="mobile-menu-user-icon" />
                  <span className="mobile-menu-user-name">{getUserDisplayName()}</span>
                </div>
              )}
              <div className="mobile-menu-item theme-toggle" onClick={toggleDarkMode}>
                {darkMode ? (
                  <>
                    <FaSun className="mobile-menu-item-icon" />
                    <span>Light Mode</span>
                  </>
                ) : (
                  <>
                    <FaMoon className="mobile-menu-item-icon" />
                    <span>Dark Mode</span>
                  </>
                )}
              </div>
              {currentUser ? (
                <div className="mobile-menu-item logout" onClick={handleLogout}>
                  <FaSignOutAlt className="mobile-menu-item-icon" />
                  <span>Sign Out</span>
                </div>
              ) : (
                <div className="mobile-menu-item login" onClick={() => navigate('/login')}>
                  <FaUser className="mobile-menu-item-icon" />
                  <span>Sign In</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
};

export default Navbar;
