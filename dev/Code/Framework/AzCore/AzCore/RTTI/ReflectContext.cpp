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
#include <AzCore/RTTI/ReflectContext.h>

#include <AzCore/std/string/string.h>

namespace AZ
{
    //=========================================================================
    // OnDemandReflectionOwner
    //=========================================================================
    OnDemandReflectionOwner::OnDemandReflectionOwner(ReflectContext& context)
        : m_reflectContext(context)
    { }

    //=========================================================================
    // AddReflectFunction
    //=========================================================================
    void OnDemandReflectionOwner::AddReflectFunction(AZ::Uuid typeId, OnDemandReflectionFunctionPtr reflectFunction)
    {
        auto& currentTypes = m_reflectContext.m_currentlyProcessingTypeIds;
        // If we're in process of reflecting this type already, don't store references to it
        if (AZStd::find(currentTypes.begin(), currentTypes.end(), typeId) != currentTypes.end())
        {
            return;
        }

        auto reflectionIt = m_reflectContext.m_onDemandReflection.find(typeId);
        if (reflectionIt == m_reflectContext.m_onDemandReflection.end())
        {
            // Capture for lambda (in case this is gone when unreflecting)
            AZ::ReflectContext* reflectContext = &m_reflectContext;
            // If it's not already reflected, add it to the list, and capture a reference to it
            AZStd::shared_ptr<OnDemandReflectionFunctionRef> reflectionPtr(reflectFunction, [reflectContext, typeId](OnDemandReflectionFunctionRef unreflectFunction)
            {
                bool isRemovingReflection = reflectContext->IsRemovingReflection();

                // Call the function in RemoveReflection mode
                reflectContext->EnableRemoveReflection();
                unreflectFunction(reflectContext);
                // Reset RemoveReflection mode
                reflectContext->m_isRemoveReflection = isRemovingReflection;

                // Remove the function from the central store (otherwise it stores an empty weak_ptr)
                reflectContext->m_onDemandReflection.erase(typeId);
            });

            // Capture reference to the reflection function
            m_reflectFunctions.emplace_back(reflectionPtr);

            // Tell the manager about the function
            m_reflectContext.m_onDemandReflection.emplace(typeId, reflectionPtr);
            m_reflectContext.m_toProcessOnDemandReflection.emplace_back(typeId, AZStd::move(reflectFunction));
        }
        else
        {
            // If it is already reflected, just capture a reference to it
            auto reflectionPtr = reflectionIt->second.lock();
            AZ_Assert(reflectionPtr, "OnDemandReflection for typed %s is missing, despite being present in the reflect context", typeId.ToString<AZStd::string>().c_str());
            if (reflectionPtr)
            {
                m_reflectFunctions.emplace_back(AZStd::move(reflectionPtr));
            }
        }
    }

    //=========================================================================
    // ReflectContext
    //=========================================================================
    ReflectContext::ReflectContext()
        : m_isRemoveReflection(false)
    { }

    //=========================================================================
    // EnableRemoveReflection
    //=========================================================================
    void ReflectContext::EnableRemoveReflection()
    {
        m_isRemoveReflection = true;
    }

    //=========================================================================
    // DisableRemoveReflection
    //=========================================================================
    void ReflectContext::DisableRemoveReflection()
    {
        m_isRemoveReflection = false;
    }

    //=========================================================================
    // IsRemovingReflection
    //=========================================================================
    bool ReflectContext::IsRemovingReflection() const
    {
        return m_isRemoveReflection;
    }

    //=========================================================================
    // IsTypeReflected
    //=========================================================================
    bool ReflectContext::IsOnDemandTypeReflected(AZ::Uuid typeId)
    {
        return m_onDemandReflection.find(typeId) != m_onDemandReflection.end();
    }

    //=========================================================================
    // ExecuteQueuedReflections
    //=========================================================================
    void ReflectContext::ExecuteQueuedOnDemandReflections()
    {
        // Need to do move so recursive definitions don't result in reprocessing the same type
        auto toProcess = AZStd::move(m_toProcessOnDemandReflection);
        m_toProcessOnDemandReflection.clear();
        for (const auto& reflectPair : toProcess)
        {
            m_currentlyProcessingTypeIds.emplace_back(reflectPair.first);
            reflectPair.second(this);
            m_currentlyProcessingTypeIds.pop_back();
        }
    }
}