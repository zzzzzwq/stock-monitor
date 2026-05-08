const app = getApp()

function request(method, path, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.apiBase + path,
      method,
      data,
      header: {
        'Content-Type': 'application/json',
        'Authorization': app.globalData.token ? 'Bearer ' + app.globalData.token : ''
      },
      success(res) {
        if (res.statusCode === 401) {
          wx.removeStorageSync('token')
          wx.reLaunch({ url: '/pages/login/login' })
          reject(new Error('未登录'))
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          reject(res.data || { error: '请求失败' })
        }
      },
      fail(err) {
        reject({ error: '网络错误', detail: err })
      }
    })
  })
}

module.exports = {
  // 认证
  wxLogin(code, nickname, avatarUrl) {
    return request('POST', '/auth/wx-login', { code, nickname, avatarUrl })
  },
  devLogin(nickname, id) {
    return request('POST', '/auth/dev-login', { nickname, id })
  },
  getMe() {
    return request('GET', '/auth/me')
  },
  updateProfile(data) {
    return request('PUT', '/auth/update-profile', data)
  },

  // 持仓
  getHoldings() {
    return request('GET', '/holdings')
  },
  addHolding(data) {
    return request('POST', '/holdings', data)
  },
  updateHolding(id, data) {
    return request('PUT', `/holdings/${id}`, data)
  },
  deleteHolding(id) {
    return request('DELETE', `/holdings/${id}`)
  },

  // 分析
  getSummary() {
    return request('GET', '/analysis/summary')
  },
  getDetail(code) {
    return request('GET', `/analysis/detail/${code}`)
  },
  getBoards() {
    return request('GET', '/analysis/boards')
  },
  nextTradingDay() {
    return request('GET', '/analysis/next-trading-day')
  },

  // 通知
  getNotifyConfig() {
    return request('GET', '/notify/config')
  },
  updateNotifyConfig(data) {
    return request('PUT', '/notify/config', data)
  }
}
