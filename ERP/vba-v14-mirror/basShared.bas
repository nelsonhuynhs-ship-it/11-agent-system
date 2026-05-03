' ============================================================
'  basShared — Shared Constants and Test Helpers
'  Extracted from erp-v14-ribbon-callbacks.bas declarations section
'  Use this module for cross-module constants and test helpers.
'  Feature-specific state stays in their own modules.
' ============================================================

Attribute VB_Name = "basShared"
Option Explicit

' ============================================================
'  CONSTANTS — Active Jobs + Quotes column layout
'  DO NOT hardcode column numbers — use these constants.
'  Single source of truth for Active Jobs 40-col layout.
' ============================================================
Public Const DATA_START_ROW As Integer = 2
Public Const QUOTES_DATA_START As Long = 5
Public Const QUOTES_HEADER_ROW As Long = 4

' Active Jobs column indices
Public Const COL_POL As Integer = 1
Public Const COL_POD As Integer = 2
Public Const COL_PLACE As Integer = 3
Public Const COL_CARRIER As Integer = 4
Public Const COL_COMMODITY As Integer = 5
Public Const COL_EFF As Integer = 6
Public Const COL_EXP As Integer = 7
Public Const COL_NOTE As Integer = 8
Public Const COL_SOURCE As Integer = 9
Public Const COL_20GP As Integer = 10
Public Const COL_40GP As Integer = 11
Public Const COL_40HQ As Integer = 12
Public Const COL_45HQ As Integer = 13
Public Const COL_40NOR As Integer = 14
Public Const COL_20RF As Integer = 15
Public Const COL_40RF As Integer = 16

' ============================================================
'  TEST HARNESS HELPERS
'  Used by E2E Python tests to inject test data and verify state.
' ============================================================
Public Function MsgBoxOrSilent(msg As String, Optional style As VbMsgBoxStyle = vbOkOnly) As VbMsgBoxResult
    ' If g_TestMode = True: suppress MsgBox for success/info, log to Debug.Print
    ' Error MsgBox (vbExclamation/vbCritical) always fires.
    If g_TestMode Then
        If style And (vbExclamation Or vbCritical) Then
            MsgBoxOrSilent = MsgBox(msg, style)
        Else
            Debug.Print "[TEST MODE] " & msg
            MsgBoxOrSilent = vbOk
        End If
    Else
        MsgBoxOrSilent = MsgBox(msg, style)
    End If
End Function

' Test state — shared across all modules via global g_TestMode, g_LastError
' Declared in erp-v14-ribbon-callbacks.bas as Public:
'   Public g_TestMode As Boolean
'   Public g_LastError As String
' These are accessed as ERPv14Ribbon.g_TestMode from other modules.
