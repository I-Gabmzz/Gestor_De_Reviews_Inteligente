import apiClient from '../services/apiClient.js'


export async function getReviews(options = {}) {
  const response = await apiClient.get('/reviews', options)
  return response.data
}

export async function getReviewById(reviewId, options = {}) {
  const response = await apiClient.get(`/reviews/${reviewId}`, options)
  return response.data
}
