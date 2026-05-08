App({
  globalData: {
    // 开发环境用 localhost，生产环境改为你的域名
    // 小程序开发工具中开启"不校验合法域名"可调试本地
    // 本地开发: http://localhost:8080/api
    // 生产环境: https://你的域名/api
    apiBase: 'http://localhost:8080/api',
    token: '',
    userInfo: null
  },

  onLaunch() {
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
    }
  },

  setApiBase(url) {
    this.globalData.apiBase = url
  },

  setToken(token) {
    this.globalData.token = token
    wx.setStorageSync('token', token)
  },

  clearToken() {
    this.globalData.token = ''
    wx.removeStorageSync('token')
  },

  isLoggedIn() {
    return !!this.globalData.token
  }
})
