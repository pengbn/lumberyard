/*
* All or portions of this file Copyright (c) Amazon.com, Inc. or its affiliates or
* its licensors.
*
* For complete copyright and license terms please see the LICENSE at the root of this
* distribution (the "License"). All use of this software is governed by the License,
* or, if provided, by the license below or the license accompanying this file. Do not
* remove or modify any license notices. This file is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
*
*/
// Original file Copyright Crytek GMBH or its affiliates, used under license.

// Description : Declaration of the DXGL wrapper for IDXGIOutput


#ifndef __CRYDXGLGIOUTPUT__
#define __CRYDXGLGIOUTPUT__

#include "CCryDXGLGIObject.hpp"

namespace NCryOpenGL
{
    struct SOutput;
}


class CCryDXGLGIOutput
    : public CCryDXGLGIObject
{
public:
    DXGL_IMPLEMENT_INTERFACE(CCryDXGLGIOutput, DXGIOutput)

    CCryDXGLGIOutput(NCryOpenGL::SOutput* pGLOutput);
    virtual ~CCryDXGLGIOutput();

    bool Initialize();
    NCryOpenGL::SOutput* GetGLOutput();

    // IDXGIOutput implementation
    HRESULT GetDesc(DXGI_OUTPUT_DESC* pDesc);
    HRESULT GetDisplayModeList(DXGI_FORMAT EnumFormat, UINT Flags, UINT* pNumModes, DXGI_MODE_DESC* pDesc);
    HRESULT FindClosestMatchingMode(const DXGI_MODE_DESC* pModeToMatch, DXGI_MODE_DESC* pClosestMatch, IUnknown* pConcernedDevice);
    HRESULT WaitForVBlank(void);
    HRESULT TakeOwnership(IUnknown* pDevice, BOOL Exclusive);
    void ReleaseOwnership(void);
    HRESULT GetGammaControlCapabilities(DXGI_GAMMA_CONTROL_CAPABILITIES* pGammaCaps);
    HRESULT SetGammaControl(const DXGI_GAMMA_CONTROL* pArray);
    HRESULT GetGammaControl(DXGI_GAMMA_CONTROL* pArray);
    HRESULT SetDisplaySurface(IDXGISurface* pScanoutSurface);
    HRESULT GetDisplaySurfaceData(IDXGISurface* pDestination);
    HRESULT GetFrameStatistics(DXGI_FRAME_STATISTICS* pStats);

protected:
    _smart_ptr<NCryOpenGL::SOutput> m_spGLOutput;
    std::vector<DXGI_MODE_DESC> m_kDisplayModes;
    DXGI_OUTPUT_DESC m_kDesc;
};

#endif //__CRYDXGLGIOUTPUT__