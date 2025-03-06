import React from "react";
import { motion } from "framer-motion";
import { FaUser, FaRobot } from "react-icons/fa";

const ChatMessage = ({ text, sender, isFirst = true, isLast = true }) => {
  // Generate a timestamp for the message
  const timestamp = new Date().toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit' 
  });
  
  // Animation variants
  const variants = {
    initial: { 
      opacity: 0, 
      y: 20,
      scale: 0.8
    },
    animate: { 
      opacity: 1, 
      y: 0,
      scale: 1
    },
    exit: {
      opacity: 0,
      scale: 0.8,
      transition: { duration: 0.2 }
    }
  };

  return (
    <motion.div
      initial="initial"
      animate="animate"
      exit="exit"
      variants={variants}
      transition={{ 
        type: "spring", 
        stiffness: 500, 
        damping: 30 
      }}
      className={`chat-message ${sender}`}
      layout
    >
      {sender === 'bot' && isFirst && (
        <div className="message-avatar bot-avatar">
          <FaRobot />
        </div>
      )}
      
      {sender === 'bot' && !isFirst && (
        <div className="message-avatar-spacer"></div>
      )}
      
      <div className="message-content">
        <p>{text}</p>
        {isLast && <span className="message-timestamp">{timestamp}</span>}
      </div>
      
      {sender === 'user' && isFirst && (
        <div className="message-avatar user-avatar">
          <FaUser />
        </div>
      )}
      
      {sender === 'user' && !isFirst && (
        <div className="message-avatar-spacer"></div>
      )}
    </motion.div>
  );
};

export default ChatMessage;
