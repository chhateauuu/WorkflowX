import React, { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { FaPaperPlane, FaSmile, FaMicrophone } from "react-icons/fa";

const MessageInput = ({ onSend }) => {
  const [message, setMessage] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const inputRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  
  // Common emojis for quick access
  const quickEmojis = ["😊", "👍", "❤️", "😂", "🎉", "👏", "🔥", "✅"];
  
  // Handle send message
  const handleSend = () => {
    if (message.trim() !== "") {
      onSend(message);
      setMessage("");
      setIsTyping(false);
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      inputRef.current.focus();
    }
  };

  // Handle key press
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  // Handle typing indicator
  const handleTyping = (e) => {
    setMessage(e.target.value);
    
    if (!isTyping) {
      setIsTyping(true);
    }
    
    // Reset typing timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    
    // Set typing timeout to false after 2 seconds of inactivity
    typingTimeoutRef.current = setTimeout(() => {
      setIsTyping(false);
    }, 2000);
  };
  
  // Add emoji to message
  const addEmoji = (emoji) => {
    setMessage(prev => prev + emoji);
    inputRef.current.focus();
  };
  
  // Close emoji picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (showEmoji && !e.target.closest('.emoji-container')) {
        setShowEmoji(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showEmoji]);
  
  // Focus input on mount
  useEffect(() => {
    inputRef.current.focus();
  }, []);

  return (
    <div className="message-input-container">
      {isTyping && (
        <motion.div 
          className="typing-indicator"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <span>You are typing...</span>
        </motion.div>
      )}
      
      <div className="message-input">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            value={message}
            onChange={handleTyping}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            rows={1}
          />
        </div>
        
        <div className="input-actions">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="send-button"
            onClick={handleSend}
            disabled={message.trim() === ""}
          >
            <FaPaperPlane />
          </motion.button>
        </div>
      </div>
    </div>
  );
};

export default MessageInput;
