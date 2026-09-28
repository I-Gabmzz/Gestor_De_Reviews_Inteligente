import apiClient from './apiClient.js'

export { getReviewById, getReviews, updateReview } from '../api/reviews.js'

export async function updateReviewStatus(reviewId, estado) {
  const { data } = await apiClient.patch(`/reviews/${reviewId}/status`, { estado })
  return data
}
