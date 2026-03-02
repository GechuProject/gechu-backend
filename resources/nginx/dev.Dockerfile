FROM nginx:latest
COPY resources/nginx/nginx.dev.conf /etc/nginx/nginx.conf
CMD ["nginx", "-g", "daemon off;"]