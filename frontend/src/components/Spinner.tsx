import { motion } from 'framer-motion';

export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <motion.div
      className="border-4 border-blue-500 border-t-transparent rounded-full"
      style={{ width: size, height: size }}
      animate={{ rotate: 360 }}
      transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
    />
  );
}
