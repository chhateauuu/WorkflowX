import React from "react";
import { motion } from "framer-motion";

const ChatMessage = ({ text, sender }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`chat-message ${sender}`}
    >
      <p>{text}</p>
    </motion.div>
  );
};

export default ChatMessage;
