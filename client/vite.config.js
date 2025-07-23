import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            // Proxy /api requests to the backend server
            '/connect': {
                target: 'https://geminichatbot-4d2f8f42c891.herokuapp.com', // Replace with your backend URL
                changeOrigin: true,
            },
        },
    },
});