import apiClient from '../services/apiClient.js'


export async function getReviews(options = {}) {
  const response = await apiClient.get('/reviews', options)
  return response.data
}

export async function getReviewById(reviewId, options = {}) {
  const response = await apiClient.get(`/reviews/${reviewId}`, options)
  return response.data
}

export async function updateReview(reviewId, changes, options = {}) {
  const response = await apiClient.patch(`/reviews/${reviewId}`, changes, options)
  return response.data
}
