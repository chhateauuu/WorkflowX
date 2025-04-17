import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Check if user is already logged in from localStorage
  useEffect(() => {
    const user = localStorage.getItem('user');
    if (user) {
      setCurrentUser(JSON.parse(user));
    }
    setLoading(false);
  }, []);

  // Login function
  const login = async (email, password) => {
    try {
      console.log('Attempting login with:', { email });
      
      // First, get user data from localStorage if we've previously stored it during registration
      const registeredUsers = JSON.parse(localStorage.getItem('registeredUsers') || '{}');
      const userData = registeredUsers[email] || { email };
      
      // Now attempt to login
      const response = await fetch('http://localhost:8000/auth/auth/jwt/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: email,
          password: password,
        }),
      });
      
      console.log('Login response status:', response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Login failed:', errorText);
        throw new Error(`Login failed: ${response.status} ${errorText}`);
      }
      
      const data = await response.json();
      console.log('Login successful, received token type:', data.token_type);
      console.log('Token first 20 chars:', data.access_token.substring(0, 20) + '...');
      
      // Get user info
      console.log('Fetching user data...');
      try {
        const userResponse = await fetch('http://localhost:8000/auth/users/me', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${data.access_token}`,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          }
        });
        
        console.log('User info response status:', userResponse.status);
        
        if (userResponse.ok) {
          const userResponseData = await userResponse.json();
          console.log('User data received:', userResponseData);
          
          // Update our cached user data with the name from the backend
          userData.name = userResponseData.name || email;
          userData._id = userResponseData.id || userResponseData._id;
          
          // Store updated user data in registeredUsers cache
          registeredUsers[email] = userData;
          localStorage.setItem('registeredUsers', JSON.stringify(registeredUsers));
        } else {
          console.warn('Failed to get user data, using previous data if available');
        }
      } catch (userError) {
        console.error('Error fetching user data:', userError);
      }
      
      // Create user object with all available data
      const user = {
        ...userData,
        email,
        token: data.access_token
      };
      
      // Ensure name is set - if not from backend, use email or default
      if (!user.name) {
        user.name = email;
      }
      
      localStorage.setItem('user', JSON.stringify(user));
      setCurrentUser(user);
      return user;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  };

  // Register function
  const register = async (name, email, password) => {
    try {
      console.log('Attempting registration with:', { email, name });
      
      const response = await fetch('http://localhost:8000/auth/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          name
        }),
      });
      
      console.log('Registration response status:', response.status);
      
      if (!response.ok) {
        const errorData = await response.json();
        console.error('Registration failed:', errorData);
        throw new Error(errorData.detail || `Registration failed: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Registration successful:', data);
      
      // Store the user data for this email
      const registeredUsers = JSON.parse(localStorage.getItem('registeredUsers') || '{}');
      registeredUsers[email] = {
        email,
        name,
        _id: data.id || data._id
      };
      localStorage.setItem('registeredUsers', JSON.stringify(registeredUsers));
      
      return data;
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  };

  // Logout function
  const logout = () => {
    localStorage.removeItem('user');
    setCurrentUser(null);
  };

  const value = {
    currentUser,
    login,
    register,
    logout,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export default AuthContext; 