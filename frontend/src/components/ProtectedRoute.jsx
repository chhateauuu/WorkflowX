import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ProtectedRoute = ({ children }) => {
  const { currentUser, loading, logout } = useAuth();
  
  // Check if token is expired
  useEffect(() => {
    if (currentUser && currentUser.token) {
      try {
        // Parse the JWT to get exp field (expiration timestamp)
        const tokenParts = currentUser.token.split('.');
        if (tokenParts.length !== 3) {
          console.error('Invalid token format');
          logout();
          return;
        }
        
        const payload = JSON.parse(atob(tokenParts[1]));
        const expTime = payload.exp * 1000; // Convert to milliseconds
        
        if (Date.now() > expTime) {
          console.log('Token expired, logging out');
          logout();
        } else {
          console.log('Token valid until:', new Date(expTime).toLocaleString());
        }
      } catch (error) {
        console.error('Error checking token validity:', error);
      }
    }
  }, [currentUser, logout]);
  
  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }
  
  if (!currentUser) {
    return <Navigate to="/login" />;
  }
  
  return children;
};

export default ProtectedRoute; 