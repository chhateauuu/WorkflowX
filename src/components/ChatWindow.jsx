import React, { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";

const ChatWindow = ({ messages }) => {
  const messagesEndRef = useRef(null);

  // Function to scroll to the bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Scroll when messages update
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="chat-window">
      {messages.map((msg, index) => (
        <ChatMessage key={index} text={msg.text} sender={msg.sender} />
      ))}
      {/* Invisible div to ensure scrolling happens correctly */}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default ChatWindow;
