import React, { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import Navbar from "./components/Navbar";
import ChatWindow from "./components/ChatWindow";
import MessageInput from "./components/MessageInput";
import Login from "./components/Login";
import Register from "./components/Register";
import Analytics from "./components/Analytics";
import ProtectedRoute from "./components/ProtectedRoute";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import "./styles.css";

// Debug component for auth issues
const DebugAuth = () => {
  const { currentUser } = useAuth();
  const [debugInfo, setDebugInfo] = useState({});
  
  useEffect(() => {
    const getRegisteredUsers = () => {
      try {
        return JSON.parse(localStorage.getItem('registeredUsers') || '{}');
      } catch (e) {
        return { error: e.message };
      }
    };
    
    setDebugInfo({
      currentUser,
      registeredUsers: getRegisteredUsers(),
      localStorage: {
        user: localStorage.getItem('user'),
        darkMode: localStorage.getItem('darkMode')
      }
    });
  }, [currentUser]);
  
  return (
    <div className="debug-container">
      <h1>Authentication Debug</h1>
      <div className="debug-section">
        <h2>Current User</h2>
        <pre>{JSON.stringify(debugInfo.currentUser, null, 2)}</pre>
      </div>
      <div className="debug-section">
        <h2>Registered Users Cache</h2>
        <pre>{JSON.stringify(debugInfo.registeredUsers, null, 2)}</pre>
      </div>
      <div className="debug-section">
        <h2>Local Storage</h2>
        <pre>{JSON.stringify(debugInfo.localStorage, null, 2)}</pre>
      </div>
    </div>
  );
};

// Main app content
const MainApp = () => {
  const [messages, setMessages] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [loading, setLoading] = useState(true);
  
  // Check for saved dark mode preference
  useEffect(() => {
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';
    setDarkMode(savedDarkMode);
    
    // Add or remove dark-mode class to body
    if (savedDarkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
    
    // Show loading animation briefly
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1000);
    
    return () => clearTimeout(timer);
  }, []);
  
  // Toggle dark mode
  const toggleDarkMode = () => {
    const newDarkMode = !darkMode;
    setDarkMode(newDarkMode);
    localStorage.setItem('darkMode', newDarkMode.toString());
    
    if (newDarkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  };

  const sendMessage = (message) => {
    if (message.trim() !== "") {
      // 1) Add user message to chat
      setMessages([...messages, { text: message, sender: "user" }]);
  
      // 2) Call the backend
      fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: message }),
      })
        .then((res) => res.json())
        .then((data) => {
          // No need to add artificial delay since we now have typing animation
          // Add the bot message to the messages array
          setMessages((prev) => [
            ...prev,
            { text: data.reply, sender: "bot" },
          ]);
        })
        .catch((error) => {
          console.error("Error calling AI endpoint:", error);
          setMessages((prev) => [
            ...prev,
            { text: "Oops, something went wrong with the AI service.", sender: "bot" },
          ]);
        });
    }
  };
  
  // Expose the sendMessage function to the window object for use by ChatWindow component
  useEffect(() => {
    window.sendMessageFromApp = sendMessage;
    return () => {
      delete window.sendMessageFromApp;
    };
  }, [messages]); // Re-assign when messages change since sendMessage captures messages in closure

  return (
    <AnimatePresence>
      {loading ? (
        <motion.div 
          className="app-loading"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          key="loader"
        >
          <div className="logo-container">
            <motion.div 
              className="logo-text"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ 
                type: "spring", 
                stiffness: 500, 
                damping: 30, 
                delay: 0.2 
              }}
            >
              WorkflowX
            </motion.div>
            <motion.div 
              className="logo-spinner"
              animate={{ rotate: 360 }}
              transition={{ 
                duration: 1.5, 
                repeat: Infinity, 
                ease: "linear" 
              }}
            />
          </div>
        </motion.div>
      ) : (
        <motion.div 
          className="app-container"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          key="app"
        >
          <Navbar darkMode={darkMode} toggleDarkMode={toggleDarkMode} />
          <div className="content-container">
            <Routes>
              <Route path="/" element={
                <div className="chat-container full-width">
                  <ChatWindow messages={messages} />
                  <MessageInput onSend={sendMessage} />
                </div>
              } />
              <Route path="/analytics" element={<Analytics />} />
            </Routes>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// App with routing
const App = () => {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route 
            path="/*" 
            element={
              <ProtectedRoute>
                <MainApp />
              </ProtectedRoute>
            } 
          />
          <Route path="/debug" element={<DebugAuth />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
};

export default App;
