FROM node:latest
EXPOSE 3000

COPY ./dataworkspace/dataworkspace/static /frontend
WORKDIR /frontend/js/react_apps
RUN npm install --no-progress --ignore-optional
CMD ["npm", "run", "dev"]
