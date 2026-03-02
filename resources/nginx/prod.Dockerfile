FROM nginx:latest
COPY resources/nginx/nginx.prod.conf /etc/nginx/nginx.conf
CMD ["nginx", "-g", "daemon off;"]