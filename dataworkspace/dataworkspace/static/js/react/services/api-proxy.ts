// @ts-nocheck
import { API_BASE_URL } from '../constants';

export default class ApiProxy {
  static async getHeaders(CSRFToken = '') {
    const headers = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(CSRFToken && { 'X-CSRFToken': CSRFToken })
    };
    return headers;
  }

  static async handleFetch(endpoint, requestOptions) {
    let data = {};
    let status = 500;
    try {
      const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        requestOptions
      );
      data = await response.json();
      status = response.status;
    } catch (error) {
      data = { message: 'Cannot reach API server', error: error };
      status = 500;
    }
    return { data, status };
  }

  static async patch(endpoint, payload, token) {
    const jsonData = JSON.stringify(payload);
    const headers = await ApiProxy.getHeaders(token);
    const requestOptions = {
      method: 'PATCH',
      headers: headers,
      body: jsonData
    };
    console.log('requestOptions', requestOptions);
    return await ApiProxy.handleFetch(endpoint, requestOptions);
  }

  static async post(endpoint, payload, token) {
    const jsonData = JSON.stringify(payload);
    const headers = await ApiProxy.getHeaders(token);
    const requestOptions = {
      method: 'POST',
      headers: headers,
      body: jsonData
    };
    return await ApiProxy.handleFetch(endpoint, requestOptions);
  }

  static async get(endpoint) {
    const headers = await ApiProxy.getHeaders();
    const requestOptions = {
      method: 'GET',
      headers: headers
    };
    return await ApiProxy.handleFetch(endpoint, requestOptions);
  }
}
