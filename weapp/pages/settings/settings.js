const api = require('../../utils/api')
const app = getApp()

Page({
  data: {
    userInfo: {},
    wechatUrl: '',
    dingtalkUrl: '',
    atMobilesStr: ''
  },

  onShow() {
    if (!app.isLoggedIn()) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.loadConfig()
  },

  async loadConfig() {
    try {
      const [user, notify] = await Promise.all([
        api.getMe(),
        api.getNotifyConfig()
      ])
      this.setData({
        userInfo: user,
        wechatUrl: notify.wechat_webhook || '',
        dingtalkUrl: notify.dingtalk_webhook || '',
        atMobilesStr: (notify.at_mobiles || []).join(',')
      })
    } catch (err) {
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  onWechatInput(e) {
    this.setData({ wechatUrl: e.detail.value })
  },
  onDingtalkInput(e) {
    this.setData({ dingtalkUrl: e.detail.value })
  },
  onMobilesInput(e) {
    this.setData({ atMobilesStr: e.detail.value })
  },

  async saveNotify() {
    try {
      const mobiles = this.data.atMobilesStr
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)

      await api.updateNotifyConfig({
        wechat_webhook: this.data.wechatUrl,
        dingtalk_webhook: this.data.dingtalkUrl,
        at_mobiles: mobiles
      })
      wx.showToast({ title: '保存成功' })
    } catch (err) {
      wx.showToast({ title: '保存失败', icon: 'none' })
    }
  },

  logout() {
    app.clearToken()
    wx.reLaunch({ url: '/pages/login/login' })
  }
})
