const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    showDevLogin: false,
    nickname: '用户'
  },

  onLoad() {
    if (app.isLoggedIn()) {
      wx.reLaunch({ url: '/pages/index/index' })
    }
  },

  onNicknameInput(e) {
    this.setData({ nickname: e.detail.value })
  },

  toggleDevLogin() {
    this.setData({ showDevLogin: !this.data.showDevLogin })
  },

  async onLogin() {
    wx.showLoading({ title: '登录中...' })

    try {
      if (this.data.showDevLogin) {
        // 开发环境登录
        const res = await api.devLogin(this.data.nickname || '用户', Date.now())
        app.setToken(res.token)
        wx.reLaunch({ url: '/pages/index/index' })
      } else {
        // 微信登录
        const { code } = await wx.login()
        const res = await api.wxLogin(code, '', '')
        app.setToken(res.token)
        wx.reLaunch({ url: '/pages/index/index' })
      }
    } catch (err) {
      wx.showToast({ title: '登录失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  }
})
