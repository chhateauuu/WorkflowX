import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ChatMessage from "./ChatMessage";
import { FaRobot } from "react-icons/fa";

const ChatWindow = ({ messages }) => {
  const messagesEndRef = useRef(null);
  const [showBotTyping, setShowBotTyping] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const [pendingBotMessages, setPendingBotMessages] = useState([]);
  const timeoutRef = useRef(null);

  // Function to scroll to the bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Function to simulate sending a welcome suggestion message
  const handleSuggestionClick = (text) => {
    // Find the parent App component's sendMessage function
    if (window.sendMessageFromApp) {
      window.sendMessageFromApp(text);
    }
    setShowWelcome(false);
  };

  // Handle showing and hiding bot typing indicator
  useEffect(() => {
    // If there's a user message added and it's the last message
    if (messages.length > 0 && messages[messages.length - 1].sender === "user") {
      // Clear any existing timeouts to avoid conflicts
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      
      // Show the typing indicator
      setShowBotTyping(true);
    }
    
    // If we have a new bot message (which would be the last message now)
    if (messages.length > 0 && messages[messages.length - 1].sender === "bot") {
      // Hide the typing indicator now that the bot has responded
      setShowBotTyping(false);
    }
    
    // Scroll to bottom whenever messages change
    scrollToBottom();
  }, [messages]);

  // Hide welcome message when conversation starts
  useEffect(() => {
    if (messages.length > 0) {
      setShowWelcome(false);
    }
  }, [messages]);

  // Group messages by sender for better visual representation
  const getGroupedMessages = () => {
    const groupedMessages = [];
    let currentGroup = [];
    
    messages.forEach((msg, index) => {
      const previousMsg = index > 0 ? messages[index - 1] : null;
      
      // Start a new group if sender changes or this is the first message
      if (!previousMsg || previousMsg.sender !== msg.sender) {
        if (currentGroup.length > 0) {
          groupedMessages.push(currentGroup);
        }
        currentGroup = [msg];
      } else {
        currentGroup.push(msg);
      }
    });
    
    // Add the last group
    if (currentGroup.length > 0) {
      groupedMessages.push(currentGroup);
    }
    
    return groupedMessages;
  };

  const groupedMessages = getGroupedMessages();

  return (
    <motion.div 
      className="chat-window-container"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="chat-header">
        <div className="chat-header-info">
          <FaRobot className="chat-header-icon" />
          <div>
            <h2 className="chat-header-title">WorkflowX Assistant</h2>
            <p className="chat-header-status">
              {showBotTyping ? "Typing..." : "Online"}
            </p>
          </div>
        </div>
      </div>
      
      <div className="chat-window">
        <AnimatePresence>
          {showWelcome && (
            <motion.div 
              className="welcome-message"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              <h3>Welcome to WorkflowX Chat</h3>
              <p>Ask me anything about workflows, tasks, or projects.</p>
              <div className="welcome-suggestions">
                <button onClick={() => handleSuggestionClick("How can you help me?")}>
                  How can you help me?
                </button>
                <button onClick={() => handleSuggestionClick("What features do you offer?")}>
                  What features do you offer?
                </button>
                <button onClick={() => handleSuggestionClick("Create a new project")}>
                  Create a new project
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        
        {groupedMessages.map((group, groupIndex) => (
          <div 
            key={groupIndex} 
            className={`message-group ${group[0].sender}-group`}
          >
            {group.map((msg, msgIndex) => (
              <ChatMessage 
                key={`${groupIndex}-${msgIndex}`} 
                text={msg.text} 
                sender={msg.sender} 
                isFirst={msgIndex === 0}
                isLast={msgIndex === group.length - 1}
              />
            ))}
          </div>
        ))}
        
        <AnimatePresence>
          {showBotTyping && (
            <motion.div 
              className="bot-typing"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className="typing-bubble"></div>
              <div className="typing-bubble"></div>
              <div className="typing-bubble"></div>
            </motion.div>
          )}
        </AnimatePresence>
        
        {/* Invisible div to ensure scrolling happens correctly */}
        <div ref={messagesEndRef} />
      </div>
    </motion.div>
  );
};

export default ChatWindow;
