import axios from "axios";

/*
  IMPORTANT:
  Use a relative URL because Flask serves the React production build
  and the API from the same server.

  Browser:
    http://192.168.1.153:9000

  API:
    http://192.168.1.153:9000/api/products
*/
const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json"
  }
});

export async function getProducts({ search = "", category = "" } = {}) {
  const response = await api.get("/products", {
    params: {
      ...(search.trim() ? { search: search.trim() } : {}),
      ...(category ? { category } : {})
    }
  });

  return response.data;
}

export default api;