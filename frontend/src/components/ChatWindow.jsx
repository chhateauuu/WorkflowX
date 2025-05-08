import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ChatMessage from "./ChatMessage";
import { FaRobot } from "react-icons/fa";

const ChatWindow = ({ messages }) => {
  const messagesEndRef = useRef(null);
  const [showWelcome, setShowWelcome] = useState(true);
  const [typingText, setTypingText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentMessage, setCurrentMessage] = useState("");
  const [displayedMessages, setDisplayedMessages] = useState([]);

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

  // Handle typing animation for bot messages
  useEffect(() => {
    // If there's a new message array, update displayed messages for user messages
    // and prepare bot messages for typing animation
    if (messages.length > 0) {
      // First add all user messages directly to displayed messages
      const userMessages = messages.filter(msg => msg.sender === "user");
      
      // Check if there's a new bot message that needs to be animated
      const lastMessage = messages[messages.length - 1];
      
      if (lastMessage.sender === "bot" && 
          (!displayedMessages.length || 
           displayedMessages[displayedMessages.length - 1]?.text !== lastMessage.text)) {
        // We have a new bot message to animate
        setCurrentMessage(lastMessage);
        setTypingText("");
        setCurrentIndex(0);
        setIsTyping(true);
        
        // Update displayed messages with all previous messages except the new bot message
        const previousMessages = messages.slice(0, messages.length - 1);
        setDisplayedMessages(previousMessages);
      } else if (lastMessage.sender === "user") {
        // If last message is from user, just make sure all messages except the last one
        // are in the displayed messages
        setDisplayedMessages(messages);
      }
    }
  }, [messages]);

  // Animation for typing effect - now with a more natural speed
  useEffect(() => {
    if (isTyping && currentMessage) {
      if (currentIndex < currentMessage.text.length) {
        // Show fewer characters per iteration for more natural typing
        const charsPerIteration = 1; // Show just one character at a time
        
        const timeout = setTimeout(() => {
          const endIndex = Math.min(currentIndex + charsPerIteration, currentMessage.text.length);
          const nextChunk = currentMessage.text.substring(currentIndex, endIndex);
          setTypingText(prev => prev + nextChunk);
          setCurrentIndex(endIndex);
        }, 25 + Math.random() * 20); // Slightly random delay between 25-45ms for natural typing
        
        return () => clearTimeout(timeout);
      } else {
        // Typing is complete, add the message to displayed messages
        setIsTyping(false);
        setDisplayedMessages(prev => [...prev, {...currentMessage, text: typingText}]);
      }
    }
  }, [isTyping, currentIndex, currentMessage, typingText]);

  // Hide welcome message when conversation starts
  useEffect(() => {
    if (messages.length > 0) {
      setShowWelcome(false);
    }
  }, [messages]);

  // Scroll to bottom whenever displayed messages or typing text changes
  useEffect(() => {
    scrollToBottom();
  }, [displayedMessages, typingText]);

  // Group messages by sender for better visual representation
  const getGroupedMessages = () => {
    const groupedMessages = [];
    let currentGroup = [];
    
    displayedMessages.forEach((msg, index) => {
      const previousMsg = index > 0 ? displayedMessages[index - 1] : null;
      
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
              {isTyping ? "Typing..." : "Online"}
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
              <FaRobot className="welcome-icon" />
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
        
        {/* Show typing animation for new bot messages */}
        {isTyping && (
          <div className="message-group bot-group">
            <div className="chat-message bot">
              <div className="message-avatar bot-avatar">
                <FaRobot />
              </div>
              <div className="message-content">
                <p>{typingText}<span className="typing-cursor">|</span></p>
              </div>
            </div>
          </div>
        )}
        
        {/* Invisible div to ensure scrolling happens correctly */}
        <div ref={messagesEndRef} />
      </div>
    </motion.div>
  );
};

export default ChatWindow;
