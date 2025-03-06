import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Navbar from "./components/Navbar";
import ChatWindow from "./components/ChatWindow";
import MessageInput from "./components/MessageInput";
import "./styles.css";

const App = () => {
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
          // Ensure typing animation shows for at least 1 second
          const responseReceivedTime = new Date().getTime();
          const minimumTypingTime = 1000; // 1 second minimum typing time
          
          setTimeout(() => {
            // data.reply is the AI's response from the server
            setMessages((prev) => [
              ...prev,
              { text: data.reply, sender: "bot" },
            ]);
          }, minimumTypingTime);
        })
        .catch((error) => {
          console.error("Error calling AI endpoint:", error);
          setTimeout(() => {
            setMessages((prev) => [
              ...prev,
              { text: "Oops, something went wrong with the AI service.", sender: "bot" },
            ]);
          }, 1000); // Still show typing for 1 second even on error
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
          <div className="chat-container">
            <ChatWindow messages={messages} />
            <MessageInput onSend={sendMessage} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default App;
