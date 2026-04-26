import { apiClient } from 'app';
import type { PendingUser, UserData } from '../apiclient/data-contracts';

export const userManagementClient = {
  /**
   * Get pending user requests for approval
   */
  async getPendingUsers(): Promise<PendingUser[]> {
    try {
      const response = await apiClient.get_pending_users();
      
      if (!response.ok) {
        throw new Error(`Failed to fetch pending users: ${response.statusText}`);
      }

      const data = await response.json();
      return data.users || [];
    } catch (error) {
      console.error('Error fetching pending users:', error);
      throw error;
    }
  },

  /**
   * Approve or reject a user request
   */
  async approveRejectUser(request: any): Promise<{ success: boolean; message: string; uid?: string }> {
    try {
      const response = await apiClient.approve_reject_user(request);
      
      if (!response.ok) {
        throw new Error(`Failed to process user request: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error processing user request:', error);
      throw error;
    }
  },

  /**
   * Get all users
   */
  async getAllUsers(): Promise<UserData[]> {
    try {
      const response = await apiClient.get_all_users({});
      
      if (!response.ok) {
        throw new Error(`Failed to fetch users: ${response.statusText}`);
      }

      const data = await response.json();
      return data.users || [];
    } catch (error) {
      console.error('Error fetching users:', error);
      throw error;
    }
  },

  /**
   * Get available domains for assignment
   */
  async getAvailableDomains(): Promise<Record<string, string>> {
    try {
      // @ts-ignore - method added in recent backend update
      const response = await apiClient.get_available_domains();
      
      if (!response.ok) {
        throw new Error(`Failed to fetch domains: ${response.statusText}`);
      }

      const data = await response.json();
      return data.domains || {};
    } catch (error) {
      console.error('Error fetching domains:', error);
      return {};
    }
  },

  /**
   * Assign a domain to a user
   */
  async assignUserDomain(userId: string, domain: string): Promise<{ success: boolean; message: string }> {
    try {
      // @ts-ignore - method added in recent backend update
      const response = await apiClient.assign_user_domain({
        userId,
        domain
      });
      
      if (!response.ok) {
        throw new Error(`Failed to assign domain: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error assigning domain:', error);
      throw error;
    }
  },
  
  /**
   * Format date from Firestore timestamp
   * @param timestamp Firestore timestamp object
   * @returns Formatted date string
   */
  formatDate(timestamp: { seconds: number; nanoseconds: number } | string | null | undefined): string {
    if (!timestamp) return 'N/A';

    let date: Date;
    if (typeof timestamp === 'string') {
      date = new Date(timestamp);
    } else if (typeof timestamp === 'object' && timestamp !== null && typeof timestamp.seconds === 'number') {
      date = new Date(timestamp.seconds * 1000);
    } else {
      // If it's an unexpected format, return 'Invalid Date' or 'N/A'
      // Or log an error and return 'N/A'
      console.warn('formatDate received an unexpected timestamp format:', timestamp);
      return 'Invalid Date'; // Or 'N/A'
    }

    // Check if the constructed date is valid
    if (isNaN(date.getTime())) {
      console.warn('formatDate resulted in an invalid date for timestamp:', timestamp);
      return 'Invalid Date'; // Or 'N/A'
    }
    
    return date.toLocaleString();
  },

  /**
   * Format role for display
   * @param role User role
   * @returns Formatted role string
   */
  formatRole(role: string): string {
    return role.replace('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
  }
};
